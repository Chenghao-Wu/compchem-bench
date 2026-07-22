#!/usr/bin/env python3
"""
Verifier for lammps-eam-lattice:
  0. ASSET INTEGRITY: the EAM potential is L4 ground truth in agent-writable
     /workspace/assets — validate pinned sha256 first.
  1. File existence + results.json schema (values/units)
  2. Log integrity: banner, Minimization stats, completion footer, no ERROR,
     >=2 thermo lines with the run starting at step 0
  3. Numerical tolerance on a0 / ecoh vs calibrated refs
  4. Consistency: results.json a0 vs final.data box; results.json ecoh vs
     the log's last thermo line
  5. L4 REAL RECOMPUTE: read_data final.data + run 0 with the pinned
     potential — the recomputed PE/atom must match the log's last thermo
     line. A fabricated final.data (wrong lattice constant) fails here.
"""
import hashlib
import json
import sys
import os
import re
import subprocess
import tempfile
import shutil

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 0: ASSET INTEGRITY ───────────────────────────────────────────────────
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

for rel_path, want_hash in refs.get("asset_hashes", {}).items():
    apath = os.path.join(WORKSPACE, rel_path)
    check(os.path.isfile(apath), f"pinned asset missing: {rel_path}")
    got_hash = _sha256(apath)
    check(got_hash == want_hash,
          f"asset {rel_path} was tampered with: sha256 {got_hash} != pinned {want_hash}")

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("log.lammps", "final.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("a0", "ecoh"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Log integrity ─────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Minimization stats" in log_content,
      "log.lammps missing 'Minimization stats' — no minimization was run")
check("Total wall time" in log_content,
      "log.lammps missing 'Total wall time' — run incomplete")
check("ERROR" not in log_content, "log.lammps contains ERROR lines")

thermo = []
in_run = False
for line in log_content.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[-\d.eE+]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

check(len(thermo) >= 2,
      f"Expected >=2 thermo lines from the minimization, got {len(thermo)}")
check(int(thermo[0].split()[0]) == 0, "Minimization thermo must start at step 0")
last_step, last_pe, last_lx = (lambda p: (int(p[0]), float(p[1]), float(p[2])))(thermo[-1].split())
log_ecoh = last_pe / 256.0
log_a0 = last_lx / 4.0

# ── Layer 3: Numerical tolerance ───────────────────────────────────────────────
check(abs(values["a0"] - refs["a0_ref"]) <= refs["a0_tol"],
      f"a0={values['a0']} differs from ref {refs['a0_ref']} by >{refs['a0_tol']} Å")
check(abs(values["ecoh"] - refs["ecoh_ref"]) <= refs["ecoh_tol"],
      f"ecoh={values['ecoh']} differs from ref {refs['ecoh_ref']} by >{refs['ecoh_tol']} eV/atom")

# ── Layer 4: Consistency (results.json ↔ log ↔ final.data) ────────────────────
with open(os.path.join(WORKSPACE, "final.data")) as f:
    data = f.read()

m = re.search(r"^\s*(\d+)\s+atoms\s*$", data, re.MULTILINE)
check(m is not None and int(m.group(1)) == 256, "final.data must contain 256 atoms")
box_m = re.findall(r"^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+[xyz]lo [xyz]hi\s*$",
                   data, re.MULTILINE)
check(len(box_m) == 3, "final.data: expected 3 box lines")
box_len = [float(b[1]) - float(b[0]) for b in box_m]
data_a0 = box_len[0] / 4.0
check(max(box_len) - min(box_len) <= 1e-6,
      f"final.data box is not cubic: {box_len}")
check(abs(values["a0"] - data_a0) <= refs["a0_box_tol"],
      f"results.json a0={values['a0']:.6f} vs final.data box/4={data_a0:.6f} "
      f"differ by >{refs['a0_box_tol']} Å")
check(abs(values["ecoh"] - log_ecoh) <= refs["ecoh_log_tol"],
      f"results.json ecoh={values['ecoh']:.6f} != log last line "
      f"{log_ecoh:.6f} eV/atom (tol {refs['ecoh_log_tol']})")

# ── Layer 5: L4 REAL RECOMPUTE — run 0 on final.data with the pinned potential ─
recompute_input = """units           metal
atom_style      atomic
boundary        p p p
read_data       final.data
pair_style      eam/alloy
pair_coeff      * * Cu_mishin1.eam.alloy Cu
neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes
thermo          1
thermo_style    custom step pe
run             0
"""

tmpdir = tempfile.mkdtemp(prefix="l4_recompute_")
try:
    with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
        f.write(recompute_input)
    shutil.copy(os.path.join(WORKSPACE, "final.data"), os.path.join(tmpdir, "final.data"))
    shutil.copy(os.path.join(WORKSPACE, "assets", "Cu_mishin1.eam.alloy"),
                os.path.join(tmpdir, "Cu_mishin1.eam.alloy"))

    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["lmp_serial", "-in", "recompute.in"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=180,
    )
    check(proc.returncode == 0,
          f"L4: LAMMPS could not read/run final.data (exit {proc.returncode}):\n"
          f"{proc.stdout[-1500:]}")
    th = re.findall(r"^\s*0\s+([-\d.eE+]+)\s*$", proc.stdout, re.MULTILINE)
    check(th, "L4: no thermo output from the 0-step run on final.data")
    re_ecoh = float(th[-1]) / 256.0
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

l4_tol = refs["l4_pe_tol"]
check(abs(re_ecoh - log_ecoh) <= l4_tol,
      f"L4: recomputed PE/atom of final.data {re_ecoh:.6f} != log last line "
      f"{log_ecoh:.6f} eV/atom (tol {l4_tol}) — final.data is not the genuine "
      f"product of the claimed minimization")

print("PASS: lammps-eam-lattice")

#!/usr/bin/env python3
"""
Verifier for lammps-data-build:
  0. ASSET INTEGRITY: xyz + EAM potential are L4 ground truth and live in
     agent-writable /workspace/assets — validate pinned sha256 first.
  1. File existence + results.json schema (values/units)
  2. Topology: atom count / type count / Masses section / box geometry
  3. Structure: fractional positions match the (hash-pinned) XYZ
  4. L4 REAL READ: LAMMPS itself does read_data + run 0 on cu.data with
     the pinned EAM potential; initial PE/atom must match the reference
     cohesive energy — a structure that only *looks* right (rounded
     lattice constant, perturbed sites) fails here.
  5. Consistency: results.json vs the data file itself
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

# ── Layer 0: ASSET INTEGRITY — never trust the workspace copies ───────────────
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
for fname in ("cu.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_atoms", "n_types", "mass_cu", "box_len"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Reference structure from the (hash-validated) XYZ ─────────────────────────
with open(os.path.join(WORKSPACE, "assets", "cu_fcc.xyz")) as f:
    xyz_lines = f.read().splitlines()
n_xyz = int(xyz_lines[0].strip())
lat = [float(x) for x in xyz_lines[1].split('Lattice="')[1].split('"')[0].split()]
ref_box = lat[0]
ref_pos = []
for line in xyz_lines[2:2 + n_xyz]:
    p = line.split()
    check(p[0] == "Cu", f"asset xyz has non-Cu species: {p[0]}")
    ref_pos.append([float(v) for v in p[1:4]])

# ── Layer 2: Topology of cu.data ───────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "cu.data")) as f:
    data = f.read()

m = re.search(r"^\s*(\d+)\s+atoms\s*$", data, re.MULTILINE)
check(m is not None, "cu.data missing 'N atoms' header")
n_atoms = int(m.group(1))
check(n_atoms == n_xyz, f"cu.data has {n_atoms} atoms (expected {n_xyz})")

m = re.search(r"^\s*(\d+)\s+atom types\s*$", data, re.MULTILINE)
check(m is not None, "cu.data missing 'N atom types' header")
n_types = int(m.group(1))
check(n_types == 1, f"cu.data must declare exactly 1 atom type, got {n_types}")

box_m = re.findall(r"^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([xyz])lo \3hi\s*$",
                   data, re.MULTILINE)
check(len(box_m) == 3, "cu.data: expected 3 box lines (xlo xhi / ylo yhi / zlo zhi)")
box_len = [float(b[1]) - float(b[0]) for b in box_m]
box_tol = refs["box_tol_A"]
for i, name in enumerate("xyz"):
    check(abs(box_len[i] - ref_box) <= box_tol,
          f"cu.data box {name}-length {box_len[i]:.6f} != xyz cell {ref_box:.6f} "
          f"(tol {box_tol})")

mm = re.search(r"Masses[^\n]*\n\s*\n((?:\s*\d+\s+[\d.]+\s*(?:#[^\n]*)?\n?)+)", data)
check(mm is not None, "cu.data: no parseable Masses section")
mass_lines = [l.split() for l in mm.group(1).strip().splitlines() if l.strip()]
check(len(mass_lines) == 1, f"cu.data Masses section must have 1 entry, got {len(mass_lines)}")
mass_cu = float(mass_lines[0][1])
check(abs(mass_cu - 63.546) <= refs["mass_tol"],
      f"cu.data Cu mass {mass_cu} != 63.546 (tol {refs['mass_tol']})")

am = re.search(r"Atoms[^\n]*\n\s*\n((?:\s*\d+\s+\d+\s+[-\d.eE+]+\s+[-\d.eE+]+\s+[-\d.eE+]+[^\n]*\n?)+)",
               data)
check(am is not None, "cu.data: no parseable 'Atoms # atomic' section")
dat_pos = []
ids = set()
for line in am.group(1).strip().splitlines():
    p = line.split()
    if len(p) < 5:
        continue
    aid = int(p[0])
    check(aid not in ids, f"cu.data: duplicate atom id {aid}")
    ids.add(aid)
    check(int(p[1]) == 1, f"cu.data atom {aid}: type {p[1]} != 1")
    dat_pos.append([float(p[2]), float(p[3]), float(p[4])])
check(len(dat_pos) == n_xyz,
      f"cu.data Atoms section has {len(dat_pos)} atoms (expected {n_xyz})")

# ── Layer 3: Structure — fractional positions match the XYZ ───────────────────
# Compare as sorted fractional sets (order need not be preserved).
frac_tol = refs["position_tol_frac"]
ref_frac = sorted(tuple(c / ref_box % 1.0 for c in p) for p in ref_pos)
dat_frac = sorted(tuple(c / box_len[0] % 1.0 for c in p) for p in dat_pos)
max_dev = 0.0
for rp, dp in zip(ref_frac, dat_frac):
    for a, b in zip(rp, dp):
        d = min(abs(a - b), 1.0 - abs(a - b))
        max_dev = max(max_dev, d)
check(max_dev <= frac_tol,
      f"cu.data positions deviate from xyz by up to {max_dev:.2e} in fractional "
      f"coords (tol {frac_tol}) — only the exact xyz structure is accepted")

# ── Layer 4: L4 REAL READ — LAMMPS read_data + run 0 with the pinned EAM ──────
recompute_input = """units           metal
atom_style      atomic
boundary        p p p
read_data       cu.data
pair_style      eam/alloy
pair_coeff      * * Cu_mishin1.eam.alloy Cu
neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes
thermo          1
thermo_style    custom step pe
run             0
"""

tmpdir = tempfile.mkdtemp(prefix="l4_read_")
try:
    with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
        f.write(recompute_input)
    shutil.copy(os.path.join(WORKSPACE, "cu.data"), os.path.join(tmpdir, "cu.data"))
    shutil.copy(os.path.join(WORKSPACE, "assets", "Cu_mishin1.eam.alloy"),
                os.path.join(tmpdir, "Cu_mishin1.eam.alloy"))

    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["lmp_serial", "-in", "recompute.in"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=180,
    )
    check(proc.returncode == 0,
          f"L4: LAMMPS could not read/run cu.data (exit {proc.returncode}):\n"
          f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    check("ERROR" not in proc.stdout,
          f"L4: LAMMPS reported an ERROR reading cu.data:\n{proc.stdout[-1500:]}")
    th = re.findall(r"^\s*0\s+([-\d.eE+]+)\s*$", proc.stdout, re.MULTILINE)
    check(th, "L4: no thermo output from the 0-step run on cu.data")
    # units metal => thermo pe is extensive (thermo_modify norm off); normalize
    re_pe = float(th[-1]) / n_atoms
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

pe_ref, pe_tol = refs["initial_pe_ref"], refs["initial_pe_tol"]
check(abs(re_pe - pe_ref) <= pe_tol,
      f"L4: initial PE/atom of cu.data {re_pe:.6f} eV differs from ref {pe_ref:.6f} "
      f"by >{pe_tol} — the structure is not the exact xyz supercell "
      f"(e.g. rounded lattice constant or perturbed sites)")

# ── Layer 5: Consistency — results.json vs the data file ───────────────────────
check(values["n_atoms"] == n_atoms,
      f"results.json n_atoms={values['n_atoms']} != cu.data {n_atoms}")
check(values["n_types"] == n_types,
      f"results.json n_types={values['n_types']} != cu.data {n_types}")
check(abs(values["mass_cu"] - mass_cu) <= refs["mass_tol"],
      f"results.json mass_cu={values['mass_cu']} != cu.data {mass_cu}")
check(abs(values["box_len"] - box_len[0]) <= box_tol,
      f"results.json box_len={values['box_len']} != cu.data {box_len[0]}")

print("PASS: lammps-data-build")

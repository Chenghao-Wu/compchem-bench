#!/usr/bin/env python3
"""
Verifier for lammps-restart-continue:
  1. File existence + results.json schema (values/units)
  2. Log integrity: banner, completion footer, no ERROR, exactly 21 thermo
     rows covering steps 1000..3000 (continuation, not a fresh run)
  3. Numerical tolerance: first-step PE / final PE / final temp vs
     calibrated refs (the restart + NVE continuation is deterministic, so
     the first PE in particular proves the restart was actually read)
  4. Consistency: results.json matches the log
  5. L4 REAL RECOMPUTE: 0-step PE evaluation of final.data must match the
     log's last thermo line — final.data must be the genuine end state of
     the claimed continuation.
"""
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

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("log.lammps", "final.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("first_step", "first_pe", "final_step", "final_pe", "final_temp"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Log integrity ─────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
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

n_expected = refs["expected_thermo_lines"]
check(len(thermo) == n_expected,
      f"Expected {n_expected} thermo lines (1000..3000 every 100), got {len(thermo)}")
first_step_log = int(thermo[0].split()[0])
last_step_log = int(thermo[-1].split()[0])
check(first_step_log == 1000,
      f"Continuation must start at step 1000 (timestep must NOT be reset), "
      f"got {first_step_log}")
check(last_step_log == 3000,
      f"Continuation must end at step 3000, got {last_step_log}")

log_first_pe = float(thermo[0].split()[2])
log_last_pe = float(thermo[-1].split()[2])
log_last_temp = float(thermo[-1].split()[1])

# ── Layer 3: Numerical tolerance (deterministic continuation) ─────────────────
check(values["first_step"] == 1000, f"first_step must be 1000, got {values['first_step']}")
check(values["final_step"] == 3000, f"final_step must be 3000, got {values['final_step']}")

check(abs(values["first_pe"] - refs["first_pe_ref"]) <= refs["first_pe_tol"],
      f"first_pe={values['first_pe']} differs from ref {refs['first_pe_ref']} by "
      f">{refs['first_pe_tol']} — the continuation does not join the "
      f"equilibrated state (restart not read, or re-initialized)")
check(abs(values["final_pe"] - refs["final_pe_ref"]) <= refs["final_pe_tol"],
      f"final_pe={values['final_pe']} differs from ref {refs['final_pe_ref']} by "
      f">{refs['final_pe_tol']}")
check(abs(values["final_temp"] - refs["final_temp_ref"]) <= refs["final_temp_tol"],
      f"final_temp={values['final_temp']} differs from ref {refs['final_temp_ref']} "
      f"by >{refs['final_temp_tol']}")

# ── Layer 4: Consistency with the log ──────────────────────────────────────────
ct, cp = refs["consistency_tol"], refs["consistency_tol"]
check(abs(values["first_pe"] - log_first_pe) <= cp,
      f"first_pe in results.json ({values['first_pe']}) != log ({log_first_pe})")
check(abs(values["final_pe"] - log_last_pe) <= cp,
      f"final_pe in results.json ({values['final_pe']}) != log ({log_last_pe})")
check(abs(values["final_temp"] - log_last_temp) <= ct,
      f"final_temp in results.json ({values['final_temp']}) != log ({log_last_temp})")

# ── Layer 5: L4 REAL RECOMPUTE — 0-step PE of final.data ──────────────────────
with open(os.path.join(WORKSPACE, "final.data")) as f:
    data_content = f.read()
m = re.search(r"^\s*(\d+)\s+atoms\s*$", data_content, re.MULTILINE)
check(m is not None and int(m.group(1)) == 500, "final.data must contain 500 atoms")

recompute_input = """units           lj
atom_style      atomic
boundary        p p p
pair_style      lj/cut 2.5
read_data       final.data
mass            1 1.0
pair_coeff      1 1 1.0 1.0 2.5
neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no
thermo          1
thermo_style    custom step pe
run             0
"""

tmpdir = tempfile.mkdtemp(prefix="l4_recompute_")
try:
    with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
        f.write(recompute_input)
    with open(os.path.join(tmpdir, "final.data"), "w") as f:
        f.write(data_content)

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
    re_pe = float(th[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

l4_tol = refs["l4_pe_tol"]
check(abs(re_pe - log_last_pe) <= l4_tol,
      f"L4: recomputed PE of final.data {re_pe:.6f} != log last thermo PE "
      f"{log_last_pe:.6f} (tol {l4_tol}) — final.data is not the genuine end "
      f"state of the claimed continuation")

print("PASS: lammps-restart-continue")

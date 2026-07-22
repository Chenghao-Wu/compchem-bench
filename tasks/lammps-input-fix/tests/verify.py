#!/usr/bin/env python3
"""
Verifier for lammps-input-fix:
  1. File existence + results.json schema (values/units)
  2. fixed.in sanity: must not still contain the broken tokens; must set
     pair_style / thermo_style / mass
  3. Log integrity: LAMMPS banner, completion footer, NO ERROR lines,
     exactly the expected thermo row count on steps 0..1000
  4. Numerical tolerance on final temp/PE vs calibrated refs (fixed seed
     and run length make the trajectory deterministic)
  5. Consistency: results.json matches the log's last thermo line
"""
import json
import sys
import os
import re

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
for fname in ("fixed.in", "log.lammps", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_step", "final_temp", "final_pe"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: fixed.in sanity ───────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "fixed.in")) as f:
    fixed = f.read()

check(not re.search(r"^\s*pair_styl\b", fixed, re.MULTILINE),
      "fixed.in still contains the misspelled 'pair_styl'")
check(not re.search(r"^\s*thermo_styl\b", fixed, re.MULTILINE),
      "fixed.in still contains the misspelled 'thermo_styl'")
check(re.search(r"^\s*pair_style\s+lj/cut\s+2\.5", fixed, re.MULTILINE),
      "fixed.in must set 'pair_style lj/cut 2.5' (intended physics unchanged)")
check(re.search(r"^\s*thermo_style\s+custom\s+step\s+temp\s+pe", fixed, re.MULTILINE),
      "fixed.in must set 'thermo_style custom step temp pe'")
check(re.search(r"^\s*mass\s+1\s+1\.0", fixed, re.MULTILINE),
      "fixed.in must set 'mass 1 1.0'")
check(re.search(r"^\s*run\s+1000\b", fixed, re.MULTILINE),
      "fixed.in must keep 'run 1000'")
check(re.search(r"^\s*velocity\s+all\s+create\s+1\.2\s+12345", fixed, re.MULTILINE),
      "fixed.in must keep the pinned velocity seed (1.2 12345)")

# ── Layer 3: Log integrity ─────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Total wall time" in log_content,
      "log.lammps missing 'Total wall time' — run incomplete")
check("ERROR" not in log_content,
      "log.lammps still contains ERROR lines — the fixed input must run cleanly")

thermo = []
in_run = False
for line in log_content.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[\d.eE+\-]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

n_expected = refs["expected_thermo_lines"]
check(len(thermo) == n_expected,
      f"Expected {n_expected} thermo lines (0..1000 every 100), got {len(thermo)}")
first_step = int(thermo[0].split()[0])
last_step = int(thermo[-1].split()[0])
check(first_step == 0 and last_step == 1000,
      f"Thermo covers steps {first_step}..{last_step} (expected 0..1000)")

# ── Layer 4: Numerical tolerance (deterministic trajectory) ───────────────────
check(values["final_step"] == 1000,
      f"final_step must be 1000, got {values['final_step']}")

temp_ref, temp_tol = refs["final_temp_ref"], refs["final_temp_tol"]
pe_ref, pe_tol = refs["final_pe_ref"], refs["final_pe_tol"]
check(abs(values["final_temp"] - temp_ref) <= temp_tol,
      f"final_temp={values['final_temp']} differs from ref {temp_ref} by >{temp_tol}")
check(abs(values["final_pe"] - pe_ref) <= pe_tol,
      f"final_pe={values['final_pe']} differs from ref {pe_ref} by >{pe_tol}")

# ── Layer 5: Consistency with log ──────────────────────────────────────────────
last = thermo[-1].split()
check(int(last[0]) == values["final_step"],
      f"final_step in results.json ({values['final_step']}) != log ({last[0]})")
check(abs(float(last[1]) - values["final_temp"]) <= refs["consistency_temp_tol"],
      f"final_temp in results.json ({values['final_temp']}) != log ({last[1]})")
check(abs(float(last[2]) - values["final_pe"]) <= refs["consistency_pe_tol"],
      f"final_pe in results.json ({values['final_pe']}) != log ({last[2]})")

print("PASS: lammps-input-fix")

#!/usr/bin/env python3
"""
Verifier for lammps-lj-melt:
  1. File existence + results.json schema (values/units)
  2. Log integrity (LAMMPS banner, correct thermo row count, Total wall time)
  3. Numerical tolerance (final temp and PE vs calibrated refs)
  4. Consistency: final_step/final_temp in results.json match the log
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
check(os.path.isfile(os.path.join(WORKSPACE, "log.lammps")), "Missing: log.lammps")
check(os.path.isfile(os.path.join(WORKSPACE, "results.json")), "Missing: results.json")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_step", "final_temp", "final_pe", "log_lines"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

check(values["final_step"] == 5000, f"final_step must be 5000, got {values['final_step']}")

# ── Layer 2: Log integrity ─────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()
    log_lines_list = log_content.splitlines()

check("LAMMPS" in log_content, "log.lammps does not contain LAMMPS version banner")
check("Total wall time" in log_content, "log.lammps missing 'Total wall time' footer — run did not complete")

# Count thermo output lines
thermo_data = []
in_run = False
for line in log_lines_list:
    stripped = line.strip()
    if re.match(r"^Step\s+", stripped, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[\d.eE+\-]+", stripped):
        thermo_data.append(stripped)
    if "Loop time" in line:
        in_run = False

expected_thermo = refs["expected_thermo_lines"]
check(
    len(thermo_data) == expected_thermo,
    f"Expected {expected_thermo} thermo lines (5000 steps / 100 interval + 1), "
    f"got {len(thermo_data)} — run may not have completed",
)

# log_lines must be the real line count of the submitted log
check(
    values["log_lines"] == len(log_lines_list),
    f"results.json log_lines={values['log_lines']} != actual log line count "
    f"{len(log_lines_list)}",
)

# ── Layer 3: Numerical tolerance ───────────────────────────────────────────────
temp = values["final_temp"]
pe = values["final_pe"]

temp_ref = refs["final_temp_ref"]
temp_tol = refs["final_temp_tol"]
pe_ref = refs["final_pe_ref"]
pe_tol = refs["final_pe_tol"]

check(
    abs(temp - temp_ref) <= temp_tol,
    f"final_temp={temp:.4f} differs from ref {temp_ref:.4f} by >{temp_tol} (LJ units)",
)
check(
    abs(pe - pe_ref) <= pe_tol,
    f"final_pe={pe:.4f} differs from ref {pe_ref:.4f} by >{pe_tol} (LJ units)",
)

# ── Layer 4: Consistency ───────────────────────────────────────────────────────
if thermo_data:
    last_parts = thermo_data[-1].split()
    log_final_step = int(last_parts[0])
    log_final_temp = float(last_parts[1])
    log_final_pe = float(last_parts[2])
    check(
        log_final_step == values["final_step"],
        f"final_step in results.json ({values['final_step']}) != log ({log_final_step})",
    )
    temp_match_tol = refs.get("consistency_temp_tol", 1e-4)
    check(
        abs(log_final_temp - values["final_temp"]) <= temp_match_tol,
        f"final_temp in results.json ({values['final_temp']}) != log ({log_final_temp})",
    )
    pe_match_tol = refs.get("consistency_pe_tol", 1e-4)
    check(
        abs(log_final_pe - values["final_pe"]) <= pe_match_tol,
        f"final_pe in results.json ({values['final_pe']}) != log ({log_final_pe})",
    )

print("PASS: lammps-lj-melt")

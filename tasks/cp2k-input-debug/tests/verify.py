#!/usr/bin/env python3
"""
Verifier for cp2k-input-debug:
  1. File existence + results.json schema (values/units)
  2. fixed.inp repair checks (typo gone, eV-unit cutoff gone, &END SCF present)
  3. Output integrity (CP2K banner, SCF converged, normal termination)
  4. log <-> results consistency (last ENERGY| line)
  5. Numerical tolerance vs calibrated refs (deterministic run)
"""
import json
import sys
import os
import re

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

ENERGY_RE = re.compile(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def last_energy(log_content):
    matches = ENERGY_RE.findall(log_content)
    if not matches:
        fail("No 'ENERGY| Total FORCE_EVAL' line found in CP2K output")
    return float(matches[-1])


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("fixed.inp", "ch4_sp.out", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "scf_converged"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: fixed.inp repair checks ───────────────────────────────────────────
with open(os.path.join(WORKSPACE, "fixed.inp")) as f:
    fixed = f.read()

check("DZVP-MOLOPT-SR-GTHH" not in fixed,
      "fixed.inp still contains the misspelled basis set DZVP-MOLOPT-SR-GTHH")
check(re.search(r"DZVP-MOLOPT-SR-GTH\b", fixed),
      "fixed.inp does not use the intended basis set DZVP-MOLOPT-SR-GTH")
check(not re.search(r"CUTOFF\s*\[eV\]", fixed),
      "fixed.inp still has the eV-unit cutoff (intended: 300 in default Hartree)")
check(re.search(r"&END\s+SCF", fixed),
      "fixed.inp is missing the &END SCF section terminator")
check("GTH-PBE-q4" in fixed and "GTH-PBE-q1" in fixed,
      "fixed.inp must keep the intended GTH-PBE pseudopotentials")

# ── Layer 3: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "ch4_sp.out")) as f:
    content = f.read()

check("CP2K" in content, "ch4_sp.out missing CP2K banner")
check("SCF run converged" in content, "ch4_sp.out: SCF did not converge")
check("PROGRAM ENDED AT" in content,
      "ch4_sp.out missing normal-termination footer 'PROGRAM ENDED AT'")
check(values["scf_converged"] is True, "scf_converged must be true")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
energy_log = last_energy(content)
energy_rep = values["total_energy"]

check(
    abs(energy_log - energy_rep) <= refs["consistency_energy_tol_Ha"],
    f"results.json energy {energy_rep:.10f} Ha != log energy {energy_log:.10f} Ha "
    f"(tol {refs['consistency_energy_tol_Ha']:.1e})",
)

# ── Layer 5: Reference tolerance (deterministic run) ───────────────────────────
energy_ref = refs["total_energy_Ha_ref"]
energy_tol = refs["total_energy_Ha_tol"]
check(
    abs(energy_rep - energy_ref) <= energy_tol,
    f"total_energy={energy_rep:.8f} Ha differs from ref {energy_ref:.8f} Ha by >{energy_tol:.2e}",
)

print("PASS: cp2k-input-debug")

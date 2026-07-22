#!/usr/bin/env python3
"""
Verifier for ase-script-debug:
  1. File existence + results.json schema (values/units)
  2. REAL RERUN (natural L4): run the agent's fixed analyze_cu.py itself —
     a non-zero exit is a hard fail — then read the results.json IT
     produces (not whatever was lying around before).
  3. REAL RECOMPUTE: the verifier independently recomputes both quantities
     with the same ASE/EMT versions (structure rebuilt from scratch) and
     compares exactly. Hardcoded constants in the script only pass if they
     happen to equal the true EMT values to tolerance.
  4. Reference tolerance vs calibrated values (refs.json).
"""
import json
import subprocess
import sys
import os

import numpy as np

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
for fname in ("analyze_cu.py", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

# ── Layer 2: REAL RERUN of the fixed script ───────────────────────────────────
os.remove(os.path.join(WORKSPACE, "results.json"))  # force the script to regenerate it
proc = subprocess.run(
    [sys.executable, "analyze_cu.py"],
    cwd=WORKSPACE, capture_output=True, text=True, timeout=180,
)
check(proc.returncode == 0,
      f"analyze_cu.py exited with code {proc.returncode} — the script is not fixed:\n"
      f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
check(os.path.isfile(os.path.join(WORKSPACE, "results.json")),
      "analyze_cu.py ran but did not produce results.json")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("energy_kj_mol_per_atom", "nn_distance"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 3: REAL RECOMPUTE — independent reference implementation ────────────
from ase.build import bulk
from ase.calculators.emt import EMT

atoms = bulk("Cu", "fcc", a=3.615)
atoms.calc = EMT()
re_e_kjmol = float(atoms.get_potential_energy()) / len(atoms) * 96.485

sc = atoms.repeat((2, 2, 2))
dm = sc.get_all_distances(mic=True)
re_nn = float(dm[dm > 0.1].min())

e_tol = refs["crossverify_energy_tol_kjmol"]
check(abs(values["energy_kj_mol_per_atom"] - re_e_kjmol) <= e_tol,
      f"energy_kj_mol_per_atom={values['energy_kj_mol_per_atom']:.6f} != "
      f"recomputed {re_e_kjmol:.6f} kJ/mol (tol {e_tol}) — wrong conversion "
      f"factor or hardcoded value")

nn_tol = refs["crossverify_nn_tol_A"]
check(abs(values["nn_distance"] - re_nn) <= nn_tol,
      f"nn_distance={values['nn_distance']:.6f} != recomputed {re_nn:.6f} Å "
      f"(tol {nn_tol})")

# ── Layer 4: Reference tolerance ───────────────────────────────────────────────
check(abs(re_e_kjmol - refs["energy_kj_mol_ref"]) <= refs["energy_kj_mol_tol"],
      f"recomputed energy {re_e_kjmol:.6f} outside ref "
      f"{refs['energy_kj_mol_ref']} ± {refs['energy_kj_mol_tol']} (image drift?)")
check(abs(re_nn - refs["nn_distance_A_ref"]) <= nn_tol,
      f"recomputed nn {re_nn:.6f} outside ref {refs['nn_distance_A_ref']} "
      f"± {nn_tol} (image drift?)")

print("PASS: ase-script-debug")

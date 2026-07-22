#!/usr/bin/env python3
"""
Verifier for ase-custom-calculator (L4 by construction):
  1. File existence + results.json schema (values/units)
  2. Import the agent's MorseCalculator from /workspace/morse_calculator.py
     (must be a Calculator subclass, no-arg construction)
  3. HIDDEN-GEOMETRY CHECK: evaluate the agent's calculator on geometries
     the agent never saw; energy must match the verifier's own analytic
     Morse implementation exactly, forces must match a finite-difference
     gradient of the verifier's energy — an energy/force inconsistency
     (chain-rule slip, missing factor, sign error) is fatal here even
     though every submitted file looks plausible.
  4. RELAXATION CHECK with the verifier's own implementation: relaxed.xyz
     must be a true force minimum of THIS potential, and reported
     energy/max_force must match the recomputed values.
  5. Reference anchors (calibrated relaxed energy).
"""
import importlib.util
import json
import sys
import os

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

D_E, A, R_E = 0.5, 1.5, 2.5  # the pinned Morse parameters


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def morse_energy(pos):
    e = 0.0
    n = len(pos)
    for i in range(n):
        for j in range(i + 1, n):
            r = np.linalg.norm(pos[i] - pos[j])
            x = np.exp(-A * (r - R_E))
            e += D_E * ((1.0 - x) ** 2 - 1.0)
    return e


def morse_forces_fd(pos, h=1e-5):
    n = len(pos)
    f = np.zeros((n, 3))
    for i in range(n):
        for k in range(3):
            dp = pos.copy(); dp[i, k] += h
            dm = pos.copy(); dm[i, k] -= h
            f[i, k] = -(morse_energy(dp) - morse_energy(dm)) / (2 * h)
    return f


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("morse_calculator.py", "relaxed.xyz", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "max_force", "n_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
check(values["n_steps"] >= 1, "n_steps must be >= 1 (the optimizer must run)")

# ── Layer 2: Import the agent's calculator ─────────────────────────────────────
from ase import Atoms
from ase.calculators.calculator import Calculator

spec = importlib.util.spec_from_file_location(
    "morse_calculator", os.path.join(WORKSPACE, "morse_calculator.py"))
check(spec is not None and spec.loader is not None,
      "cannot import morse_calculator.py")
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except Exception as e:
    fail(f"morse_calculator.py failed to import: {e}")

MorseCalculator = getattr(module, "MorseCalculator", None)
check(MorseCalculator is not None, "morse_calculator.py defines no MorseCalculator")
check(isinstance(MorseCalculator, type) and issubclass(MorseCalculator, Calculator),
      "MorseCalculator must subclass ase.calculators.calculator.Calculator")
try:
    agent_calc = MorseCalculator()
except Exception as e:
    fail(f"MorseCalculator() with no arguments failed: {e}")

# ── Layer 3: HIDDEN-GEOMETRY energy/force check ────────────────────────────────
hidden = [
    np.array([[0.0, 0.0, 0.0], [2.2, 0.0, 0.0]]),
    np.array([[0.0, 0.0, 0.0], [3.1, 0.0, 0.0]]),
    np.array([[0.0, 0.0, 0.0], [2.4, 0.0, 0.0], [1.2, 1.9, 0.5]]),
]

e_tol = refs["hidden_energy_tol_eV"]
f_tol = refs["hidden_force_tol_eV_per_A"]
for ci, pos in enumerate(hidden, start=1):
    atoms = Atoms("Cu" * len(pos), positions=pos)
    atoms.calc = MorseCalculator()  # fresh instance per config
    try:
        e_agent = float(atoms.get_potential_energy())
        f_agent = atoms.get_forces()
    except Exception as e:
        fail(f"agent calculator failed on hidden config {ci}: {e}")

    e_ref = morse_energy(pos)
    check(abs(e_agent - e_ref) <= e_tol,
          f"hidden config {ci}: agent energy {e_agent:.10f} != analytic Morse "
          f"{e_ref:.10f} eV (tol {e_tol}) — the potential is not the pinned one")

    f_fd = morse_forces_fd(pos)
    fd_err = float(abs(f_agent - f_fd).max())
    check(fd_err <= f_tol,
          f"hidden config {ci}: agent forces deviate from the finite-difference "
          f"gradient by {fd_err:.2e} eV/Å (tol {f_tol}) — forces inconsistent "
          f"with the potential (chain-rule slip?)")

# ── Layer 4: RELAXATION CHECK with the verifier's implementation ───────────────
from ase.io import read

relaxed = read(os.path.join(WORKSPACE, "relaxed.xyz"))
check(len(relaxed) == refs["n_atoms_expected"],
      f"relaxed.xyz has {len(relaxed)} atoms (expected {refs['n_atoms_expected']})")
check(set(relaxed.get_chemical_symbols()) == {"Cu"}, "expected pure Cu cluster")

pos = relaxed.get_positions()
e_rel = morse_energy(pos)
f_rel_fd = morse_forces_fd(pos)
fmax_rel = float(np.max(np.linalg.norm(f_rel_fd, axis=1)))
check(fmax_rel < refs["fmax_threshold_eV_per_A"],
      f"relaxed.xyz is not a force minimum of the pinned potential: "
      f"fmax {fmax_rel:.4f} >= {refs['fmax_threshold_eV_per_A']} eV/Å "
      f"(fabricated relaxation?)")

check(abs(e_rel - values["final_energy"]) <= refs["crossverify_energy_tol_eV"],
      f"reported final_energy {values['final_energy']:.8f} != verifier's "
      f"energy of relaxed.xyz {e_rel:.8f} eV")
check(abs(fmax_rel - values["max_force"]) <= refs["crossverify_fmax_tol"],
      f"reported max_force {values['max_force']:.5f} != recomputed "
      f"{fmax_rel:.5f} (tol {refs['crossverify_fmax_tol']})")

# ── Layer 5: Reference anchors ────────────────────────────────────────────────
check(abs(e_rel - refs["final_energy_eV_ref"]) <= refs["final_energy_eV_tol"],
      f"relaxed energy {e_rel:.8f} eV differs from calibrated ref "
      f"{refs['final_energy_eV_ref']:.8f} by > {refs['final_energy_eV_tol']}")

print("PASS: ase-custom-calculator")

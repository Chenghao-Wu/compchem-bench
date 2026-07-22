#!/usr/bin/env python3
"""
Verifier for ase-geoopt-h2o:
  1. File existence + results.json schema (values/units)
  2. Trajectory integrity (readable, >=2 frames, H2O stoichiometry)
  3. Self-reported sanity (fmax < threshold, n_steps >= 1)
  4. REAL RECOMPUTE (cross-verify): attach the pinned LennardJones
     calculator to the last frame and recompute energy/forces from the
     geometry itself. The reported energy/fmax/bond must match the
     recomputed values, and the recomputed fmax must satisfy the
     convergence threshold. Stored trajectory energies/forces are ignored
     — they can be fabricated; positions cannot (a fabricated geometry
     will not be a force minimum of the pinned potential).
  5. Reference tolerance vs calibrated energy/bond (refs.json).

Any anomaly in the recompute layer is a hard fail — there is no warning
fallback.
"""
import json
import sys
import os
from typing import List

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

# Pinned calculator parameters (must match instruction.md exactly)
LJ_EPSILON = 0.01
LJ_SIGMA = 1.0
LJ_RC = 5.0


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(condition, msg):
    if not condition:
        fail(msg)


# ── Load refs ─────────────────────────────────────────────────────────────────
with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("opt.traj", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing file: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

REQUIRED = ("final_energy", "max_force", "n_steps", "oh_bond_length")
for key in REQUIRED:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Trajectory integrity ──────────────────────────────────────────────
import numpy as np
from ase.io import read
from ase import Atoms as AseAtoms

traj: List[AseAtoms] = read(os.path.join(WORKSPACE, "opt.traj"), index=":")  # type: ignore[assignment]
check(len(traj) >= 2, f"opt.traj has {len(traj)} frame(s); expected >= 2 (initial + optimized)")
last_frame: AseAtoms = traj[-1]
check(len(last_frame) == 3, f"Expected 3 atoms (H2O), got {len(last_frame)}")
symbols = sorted(last_frame.get_chemical_symbols())
check(symbols == ["H", "H", "O"], f"Expected O+2H, got {symbols}")

# ── Layer 3: Self-reported sanity ──────────────────────────────────────────────
check(
    values["max_force"] < refs["fmax_threshold_eV_per_A"],
    f"reported max_force {values['max_force']:.4f} >= threshold "
    f"{refs['fmax_threshold_eV_per_A']} eV/Å",
)
check(values["n_steps"] >= 1, "n_steps must be >= 1 (optimization must run)")

# ── Layer 4: REAL RECOMPUTE with the pinned calculator ────────────────────────
from ase.calculators.lj import LennardJones

recomputed = last_frame.copy()
recomputed.calc = LennardJones(epsilon=LJ_EPSILON, sigma=LJ_SIGMA, rc=LJ_RC)
e_re = float(recomputed.get_potential_energy())
f_re = recomputed.get_forces()
fmax_re = float(np.max(np.linalg.norm(f_re, axis=1)))
o_idx = [i for i, s in enumerate(recomputed.get_chemical_symbols()) if s == "O"][0]
h_idx = [i for i, s in enumerate(recomputed.get_chemical_symbols()) if s == "H"]
bond_re = float(np.linalg.norm(recomputed.positions[h_idx[0]] - recomputed.positions[o_idx]))

e_tol = refs["crossverify_energy_tol_eV"]
check(
    abs(e_re - values["final_energy"]) <= e_tol,
    f"Cross-verify energy: recomputed {e_re:.8f} eV vs results.json "
    f"{values['final_energy']:.8f} eV (diff {abs(e_re - values['final_energy']):.2e}, "
    f"tol {e_tol:.2e}) — trajectory energy is not the pinned-calculator energy "
    f"of the final geometry",
)

check(
    fmax_re < refs["fmax_threshold_eV_per_A"],
    f"Cross-verify force: recomputed fmax {fmax_re:.4f} eV/Å >= threshold "
    f"{refs['fmax_threshold_eV_per_A']} — final geometry is NOT an optimized minimum "
    f"of the pinned potential (fabricated trajectory?)",
)

f_tol = refs["crossverify_fmax_tol_eV_per_A"]
check(
    abs(fmax_re - values["max_force"]) <= f_tol,
    f"Cross-verify fmax: recomputed {fmax_re:.6f} vs reported {values['max_force']:.6f} "
    f"(tol {f_tol}) — reported force does not match the final geometry",
)

b_tol = refs["crossverify_bond_tol_A"]
check(
    abs(bond_re - values["oh_bond_length"]) <= b_tol,
    f"Cross-verify bond: geometry O-H {bond_re:.4f} Å vs reported "
    f"{values['oh_bond_length']:.4f} Å (tol {b_tol})",
)

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
check(
    abs(e_re - refs["final_energy_eV_ref"]) <= refs["final_energy_eV_tol"],
    f"final energy {e_re:.8f} eV differs from ref {refs['final_energy_eV_ref']:.8f} "
    f"by > {refs['final_energy_eV_tol']:.2e}",
)
check(
    abs(bond_re - refs["oh_bond_A_ref"]) <= refs["oh_bond_A_tol"],
    f"O-H bond {bond_re:.4f} Å differs from ref {refs['oh_bond_A_ref']:.4f} "
    f"by > {refs['oh_bond_A_tol']}",
)

print("PASS: ase-geoopt-h2o")

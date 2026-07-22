#!/usr/bin/env python3
"""
Verifier for ase-structure-build:
  1. File existence + results.json schema (values/units)
  2. Structure identity: 256 atoms, all Cu, cubic cell of the expected edge
  3. STRUCTURAL FINGERPRINT (recompute): nearest-neighbor distance and
     12-fold coordination of EVERY atom under minimum-image convention —
     an fcc lattice is fully characterized by this; wrong lattices (sc,
     bcc, hcp, random) or wrong lattice constants fail. Deterministic, so
     there is no separate L4: the check IS a full re-derivation.
  4. Reference tolerance vs calibrated values (refs.json).
"""
import json
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
for fname in ("cu_supercell.xyz", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_atoms", "lattice_constant", "cell_length"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Structure identity ────────────────────────────────────────────────
from ase.io import read

atoms = read(os.path.join(WORKSPACE, "cu_supercell.xyz"))
n_expected = refs["n_atoms_expected"]
check(len(atoms) == n_expected,
      f"cu_supercell.xyz has {len(atoms)} atoms (expected {n_expected})")
check(set(atoms.get_chemical_symbols()) == {"Cu"},
      f"expected pure Cu, got {sorted(set(atoms.get_chemical_symbols()))}")

cell = np.array(atoms.cell)
cell_len = refs["cell_length_A_ref"]
ctol = refs["cell_length_A_tol"]
check(abs(np.diag(cell) - cell_len).max() <= ctol,
      f"cell diagonal {np.diag(cell)} != {cell_len} ± {ctol} Å")
check(abs(cell - np.diag(np.diag(cell))).max() <= 1e-6,
      f"cell is not orthogonal: {cell.tolist()}")

check(values["n_atoms"] == n_expected,
      f"results.json n_atoms={values['n_atoms']} != {n_expected}")

# ── Layer 3: STRUCTURAL FINGERPRINT — nn distance + 12-fold coordination ──────
atoms.pbc = True
pos = atoms.get_positions()
cell_arr = np.array(atoms.cell)

# minimum-image pairwise distances (orthogonal cell)
frac = atoms.get_scaled_positions() % 1.0
dfrac = frac[:, None, :] - frac[None, :, :]
dfrac -= np.round(dfrac)
dist = np.linalg.norm(dfrac @ cell_arr, axis=-1)
np.fill_diagonal(dist, np.inf)

nn_dist = float(dist.min())
nn_ref = refs["nn_distance_A_ref"]
nn_tol = refs["nn_distance_A_tol"]
check(abs(nn_dist - nn_ref) <= nn_tol,
      f"nearest-neighbor distance {nn_dist:.6f} Å != fcc value {nn_ref:.6f} "
      f"± {nn_tol} (not an fcc lattice with the required lattice constant?)")

coordination = (dist < nn_ref + 5 * nn_tol).sum(axis=1)
bad = int((coordination != 12).sum())
check(bad == 0,
      f"{bad} atom(s) do not have exactly 12 nearest neighbors at the fcc "
      f"distance — the structure is not a perfect fcc lattice")

# ── Layer 4: results.json consistency + reference tolerance ───────────────────
check(abs(values["lattice_constant"] - refs["lattice_constant_A_ref"]) <= nn_tol,
      f"lattice_constant={values['lattice_constant']} != ref "
      f"{refs['lattice_constant_A_ref']}")
check(abs(values["cell_length"] - cell_len) <= ctol,
      f"cell_length={values['cell_length']} != ref {cell_len} ± {ctol}")
check(abs(values["cell_length"] - float(np.diag(cell)[0])) <= ctol,
      f"reported cell_length {values['cell_length']} inconsistent with the "
      f"xyz cell {float(np.diag(cell)[0]):.6f}")

print("PASS: ase-structure-build")

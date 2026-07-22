#!/usr/bin/env python3
"""Analyze fcc Cu with the EMT potential.

Computes the EMT energy per atom (converted to kJ/mol) and the
nearest-neighbor distance of fcc Cu (a = 3.615 A), writes results.json.

NOTE: this script currently crashes, and once the crash is fixed the
reported energy is implausible for copper. Find and fix all bugs.
"""
import json
import numpy as np
from ase.build import bulk
from ase.calculators.emt import EMT

A = 3.615  # fcc Cu lattice constant, angstrom

atoms = bulk("Cu", "fcc", a=A)  # primitive cell, pbc on
atoms.set_calculator(EMT())

e_atom_ev = np.float(atoms.get_potential_energy()) / len(atoms)

EV_TO_KJMOL = 23.0609  # eV -> kJ/mol conversion factor
e_atom_kjmol = e_atom_ev * EV_TO_KJMOL

# Nearest-neighbor distance from a 2x2x2 repeat with minimum-image convention
sc = atoms.repeat((2, 2, 2))
dm = sc.get_all_distances(mic=True)
nn = float(dm[dm > 0.1].min())

results = {
    "values": {
        "energy_kj_mol_per_atom": e_atom_kjmol,
        "nn_distance": nn,
    },
    "units": {
        "energy_kj_mol_per_atom": "kJ/mol",
        "nn_distance": "Å",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E = {e_atom_kjmol:.6f} kJ/mol/atom, nn = {nn:.6f} Å")

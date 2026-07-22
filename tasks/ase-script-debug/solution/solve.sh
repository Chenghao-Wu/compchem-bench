#!/usr/bin/env bash
# Oracle solution: fix the broken script (np.float -> float; kcal factor ->
# kJ factor; deprecated set_calculator -> .calc) and run it for real.
set -euo pipefail
cd /workspace

cat > analyze_cu.py << 'PYEOF'
#!/usr/bin/env python3
"""Analyze fcc Cu with the EMT potential (fixed version)."""
import json
import numpy as np
from ase.build import bulk
from ase.calculators.emt import EMT

A = 3.615  # fcc Cu lattice constant, angstrom

atoms = bulk("Cu", "fcc", a=A)  # primitive cell, pbc on
atoms.calc = EMT()

e_atom_ev = float(atoms.get_potential_energy()) / len(atoms)

EV_TO_KJMOL = 96.485  # eV -> kJ/mol conversion factor
e_atom_kjmol = e_atom_ev * EV_TO_KJMOL

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
PYEOF

python3 analyze_cu.py

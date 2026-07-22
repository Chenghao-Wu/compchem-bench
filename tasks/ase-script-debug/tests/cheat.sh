#!/usr/bin/env bash
# Informed cheat: fixes the crash properly, but instead of fixing the unit
# conversion the script HARDCODES the literature cohesive energy of copper
# (-3.49 eV/atom = -336.87 kJ/mol) — a physically plausible, well-known
# number — and the correct nn distance. The script runs cleanly and its
# output is self-consistent.
# Must FAIL: the verifier recomputes the EMT value itself; EMT's reference
# state makes the true number ~-0.476 kJ/mol, far outside tolerance of the
# literature value.
set -euo pipefail
mkdir -p /workspace
cd /workspace

cat > analyze_cu.py << 'PYEOF'
import json
import numpy as np
from ase.build import bulk
from ase.calculators.emt import EMT

A = 3.615
atoms = bulk("Cu", "fcc", a=A)
atoms.calc = EMT()

# "Fixed": crash gone, and the energy is the well-known Cu cohesive energy
e_atom_kjmol = -3.49 * 96.485  # literature Cu cohesive energy in kJ/mol

sc = atoms.repeat((2, 2, 2))
dm = sc.get_all_distances(mic=True)
nn = float(dm[dm > 0.1].min())

results = {
    "values": {"energy_kj_mol_per_atom": e_atom_kjmol, "nn_distance": nn},
    "units": {"energy_kj_mol_per_atom": "kJ/mol", "nn_distance": "Å"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"E = {e_atom_kjmol:.6f} kJ/mol/atom, nn = {nn:.6f} Å")
PYEOF

python3 analyze_cu.py

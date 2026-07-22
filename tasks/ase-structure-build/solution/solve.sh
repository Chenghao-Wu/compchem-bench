#!/usr/bin/env bash
# Oracle solution: build the 4x4x4 fcc Cu supercell with ASE and write
# cu_supercell.xyz + results.json. Real construction, no hardcoded answers.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from ase.build import bulk
from ase.io import write

A = 3.615  # fcc Cu lattice constant, Å

atoms = bulk("Cu", "fcc", a=A, cubic=True).repeat((4, 4, 4))

write("cu_supercell.xyz", atoms, format="extxyz")

results = {
    "values": {
        "n_atoms": len(atoms),
        "lattice_constant": A,
        "cell_length": float(atoms.cell[0, 0]),
    },
    "units": {
        "n_atoms": "1",
        "lattice_constant": "Å",
        "cell_length": "Å",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Built {len(atoms)}-atom fcc Cu supercell, cell {atoms.cell[0,0]:.4f} Å")
PYEOF

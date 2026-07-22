#!/usr/bin/env bash
# Informed cheat: knows the deliverables and the expected metadata, but does
# NOT build an fcc lattice. Writes 256 Cu atoms on a SIMPLE CUBIC 4x8x8
# grid inside the correct 14.46 Å cubic cell — right atom count, right
# cell, right results.json numbers, wrong lattice type.
# Must FAIL: the verifier checks the nearest-neighbor distance (1.8075 vs
# the fcc 2.5562 Å) and the 12-fold coordination of every atom.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
from ase import Atoms
from ase.io import write

L = 14.46  # 4 * 3.615
s = L / 8  # simple-cubic spacing
pos = [[i * s, j * s, k * s] for i in range(4) for j in range(8) for k in range(8)]
assert len(pos) == 256
atoms = Atoms("Cu256", positions=pos, cell=[L, L, L], pbc=True)
write("cu_supercell.xyz", atoms, format="extxyz")

results = {
    "values": {"n_atoms": 256, "lattice_constant": 3.615, "cell_length": 14.46},
    "units": {"n_atoms": "1", "lattice_constant": "Å", "cell_length": "Å"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged simple-cubic 'fcc' supercell written")
PYEOF

#!/usr/bin/env bash
# Informed cheat: a forger who knows FCC Cu from textbooks. Builds a
# syntactically perfect cu.data with the right atom count, one type, the
# right mass — but hand-rolls the lattice with the commonly quoted rounded
# value a = 3.60 Å (box 10.8 Å) instead of the xyz's exact 3.615 Å.
# Passes layers 1-3 and 5: fractional positions of a perfect FCC lattice
# are IDENTICAL for any a, the box differs from the xyz cell by only
# 0.045 Å (inside the box tolerance), topology/masses are right, and
# results.json is self-consistent.
# Must FAIL at layer 4: LAMMPS read_data + run 0 with the pinned EAM
# potential gives an initial PE/atom measurably different from the
# a=3.615 reference — the fourth layer is the real gate.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

a = 3.60  # rounded textbook value — NOT the xyz's 3.615
basis = [(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]
atoms = []
for i in range(3):
    for j in range(3):
        for k in range(3):
            for b in basis:
                atoms.append(((i + b[0]) * a, (j + b[1]) * a, (k + b[2]) * a))
L = 3 * a

with open("cu.data", "w") as f:
    f.write("hand-built FCC Cu data\n\n")
    f.write(f"{len(atoms)} atoms\n1 atom types\n\n")
    f.write(f"0.0 {L:.6f} xlo xhi\n0.0 {L:.6f} ylo yhi\n0.0 {L:.6f} zlo zhi\n\n")
    f.write("Masses\n\n1 63.546\n\nAtoms # atomic\n\n")
    for i, (x, y, z) in enumerate(atoms, start=1):
        f.write(f"{i} 1 {x:.6f} {y:.6f} {z:.6f}\n")

results = {
    "values": {"n_atoms": len(atoms), "n_types": 1, "mass_cu": 63.546, "box_len": L},
    "units": {"n_atoms": "1", "n_types": "1", "mass_cu": "amu", "box_len": "Å"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged cu.data with rounded a=3.60 Å (fractional positions identical)")
PYEOF

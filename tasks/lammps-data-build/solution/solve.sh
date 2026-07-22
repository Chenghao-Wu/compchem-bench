#!/usr/bin/env bash
# Oracle solution for lammps-data-build.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json

# Parse the extended XYZ
with open("/workspace/assets/cu_fcc.xyz") as f:
    lines = f.read().splitlines()
n = int(lines[0].strip())
comment = lines[1]
lat_str = comment.split('Lattice="')[1].split('"')[0]
lat = [float(x) for x in lat_str.split()]
box_len = lat[0]  # cubic cell

atoms = []
for line in lines[2:2 + n]:
    p = line.split()
    assert p[0] == "Cu"
    atoms.append(tuple(float(v) for v in p[1:4]))
assert len(atoms) == n

# Write the LAMMPS data file (atom_style atomic: id type x y z)
with open("cu.data", "w") as f:
    f.write("LAMMPS data file for FCC Cu (from cu_fcc.xyz)\n\n")
    f.write(f"{n} atoms\n")
    f.write("1 atom types\n\n")
    f.write(f"0.0 {box_len:.6f} xlo xhi\n")
    f.write(f"0.0 {box_len:.6f} ylo yhi\n")
    f.write(f"0.0 {box_len:.6f} zlo zhi\n\n")
    f.write("Masses\n\n")
    f.write("1 63.546\n\n")
    f.write("Atoms # atomic\n\n")
    for i, (x, y, z) in enumerate(atoms, start=1):
        f.write(f"{i} 1 {x:.6f} {y:.6f} {z:.6f}\n")

results = {
    "values": {
        "n_atoms": n,
        "n_types": 1,
        "mass_cu": 63.546,
        "box_len": box_len,
    },
    "units": {
        "n_atoms": "1",
        "n_types": "1",
        "mass_cu": "amu",
        "box_len": "Å",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"cu.data: {n} atoms, box {box_len:.6f} Å")
PYEOF

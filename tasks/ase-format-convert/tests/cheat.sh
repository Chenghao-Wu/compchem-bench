#!/usr/bin/env bash
# Informed cheat: produces a PERFECT nacl.extxyz, but the LAMMPS data file
# is hand-rolled with the Na/Cl atom types SWAPPED (Na positions carry the
# Cl mass/type and vice versa) while results.json truthfully reports the
# file's own mapping. Superficially everything parses and the metadata is
# self-consistent.
# Must FAIL: the verifier compares element-resolved positions against the
# CIF — swapped types put "Na" where Cl belongs — and the Masses-based
# mapping check exposes the swap as well.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
from ase.io import read, write

atoms = read("/workspace/assets/nacl.cif")
write("nacl.extxyz", atoms, format="extxyz")

# Swapped mapping on purpose: Cl positions as type 1 (with Cl mass on 2? no —
# the cheat labels Na positions as Cl and Cl positions as Na).
swapped = atoms.copy()
symbols = ["Cl" if s == "Na" else "Na" for s in swapped.get_chemical_symbols()]
swapped.set_chemical_symbols(symbols)
write("nacl.data", swapped, format="lammps-data", atom_style="atomic",
      specorder=["Cl", "Na"])  # Cl=1, Na=2 in the forged file

results = {
    "values": {"n_atoms": 8, "n_types": 2, "type_na": 2, "type_cl": 1},
    "units": {"n_atoms": "1", "n_types": "1", "type_na": "1", "type_cl": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged type-swapped nacl.data written")
PYEOF

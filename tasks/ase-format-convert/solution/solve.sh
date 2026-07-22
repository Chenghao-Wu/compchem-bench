#!/usr/bin/env bash
# Oracle solution: convert the CIF to extxyz + LAMMPS data with ASE.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from ase.io import read, write

atoms = read("/workspace/assets/nacl.cif")

write("nacl.extxyz", atoms, format="extxyz")
# specorder pins a deterministic element->type mapping (Na=1, Cl=2)
write("nacl.data", atoms, format="lammps-data", atom_style="atomic",
      specorder=["Na", "Cl"])

results = {
    "values": {"n_atoms": len(atoms), "n_types": 2, "type_na": 1, "type_cl": 2},
    "units": {"n_atoms": "1", "n_types": "1", "type_na": "1", "type_cl": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Converted {len(atoms)} atoms to nacl.extxyz + nacl.data (Na=1, Cl=2)")
PYEOF

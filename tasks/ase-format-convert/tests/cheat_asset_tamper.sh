#!/usr/bin/env bash
# Informed cheat (asset-tampering): the verifier derives the
# conversion ground truth from /workspace/assets/nacl.cif — an agent-WRITABLE
# path. A forger who swaps the Na/Cl species labels in the CIF (same lattice,
# same atom count, so the Layer-5 anchors still hold) and then converts the
# TAMPERED CIF with a perfectly consistent pipeline passes every structural
# layer: extxyz fidelity, the LAMMPS-data type mapping (derived from the
# tampered CIF), and the LAMMPS read_data + run 0.
#
# Must FAIL: refs.json pins sha256(nacl.cif) and Layer 0 validates it before
# any use — a tampered CIF is a hard fail.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from ase.io import read, write

# Tamper: exchange Na and Cl species labels in the trusted CIF.
atoms = read("/workspace/assets/nacl.cif")
swapped = ["Cl" if s == "Na" else "Na" for s in atoms.get_chemical_symbols()]
atoms.set_chemical_symbols(swapped)
write("/workspace/assets/nacl.cif", atoms, format="cif")

# Convert the tampered CIF — internally fully consistent.
tampered = read("/workspace/assets/nacl.cif")
write("nacl.extxyz", tampered, format="extxyz")
write("nacl.data", tampered, format="lammps-data", atom_style="atomic",
      specorder=["Na", "Cl"])

results = {
    "values": {"n_atoms": len(tampered), "n_types": 2, "type_na": 1, "type_cl": 2},
    "units": {"n_atoms": "1", "n_types": "1", "type_na": "1", "type_cl": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Converted tampered CIF ({len(tampered)} atoms, Na/Cl swapped)")
PYEOF

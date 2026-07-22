#!/usr/bin/env bash
# Informed cheat: a forger who knows RDKit but does NOT follow the pinned
# pipeline — embeds with a different seed and skips the MMFF optimization,
# then honestly reports the TRUE MMFF energy of that structure (so even a
# verifier that only recomputes the submitted geometry's energy would
# pass).
# Must FAIL twice over:
#   - re-optimization drops the energy (structure is not an MMFF minimum)
#   - the energy is not the pinned-seed reference energy
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

with open("/workspace/assets/target.smi") as f:
    smiles = f.read().strip()

mol = Chem.AddHs(Chem.MolFromSmiles(smiles))

# Wrong seed, NO optimization
params = AllChem.ETKDGv3()
params.randomSeed = 42
AllChem.EmbedMolecule(mol, params)

props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
energy = float(AllChem.MMFFGetMoleculeForceField(mol, props).CalcEnergy())

with open("conformer.sdf", "w") as f:
    w = Chem.SDWriter(f)
    w.write(mol)
    w.close()

results = {
    "values": {
        "mmff_energy": energy,
        "n_rotatable_bonds": int(Descriptors.NumRotatableBonds(mol)),
        "n_heavy_atoms": int(mol.GetNumHeavyAtoms()),
    },
    "units": {
        "mmff_energy": "kcal/mol",
        "n_rotatable_bonds": "1",
        "n_heavy_atoms": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged conformer (wrong seed, unoptimized), honestly reported E={energy:.6f}")
PYEOF

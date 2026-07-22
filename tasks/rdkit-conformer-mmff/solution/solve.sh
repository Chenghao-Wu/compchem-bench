#!/usr/bin/env bash
# Oracle solution for rdkit-conformer-mmff.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

with open("/workspace/assets/target.smi") as f:
    smiles = f.read().strip()

mol = Chem.AddHs(Chem.MolFromSmiles(smiles))

params = AllChem.ETKDGv3()
params.randomSeed = 0xF00D
status = AllChem.EmbedMolecule(mol, params)
if status != 0:
    raise RuntimeError(f"Embedding failed with status {status}")

conv = AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94")
# conv == 0 means converged — assert it so the oracle never emits an
# un-optimized conformer silently
if conv != 0:
    raise RuntimeError(f"MMFF optimization did not converge (status {conv})")

props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
ff = AllChem.MMFFGetMoleculeForceField(mol, props)
energy = float(ff.CalcEnergy())

with open("conformer.sdf", "w") as f:
    writer = Chem.SDWriter(f)
    writer.write(mol)
    writer.close()

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

print(f"MMFF94 energy: {energy:.6f} kcal/mol (converged={conv == 0}), "
      f"rotatable={results['values']['n_rotatable_bonds']}, heavy={results['values']['n_heavy_atoms']}")
PYEOF

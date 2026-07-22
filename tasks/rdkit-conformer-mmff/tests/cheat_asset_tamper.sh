#!/usr/bin/env bash
# Informed cheat (asset-tampering): the verifier defines the
# target molecule by reading /workspace/assets/target.smi — an agent-WRITABLE
# path. A forger who replaces the target with a trivial molecule (ethanol)
# and runs the real ETKDG+MMFF pipeline on it produces a conformer that
# passes molecular identity (vs the tampered target), the MMFF recompute,
# the re-optimization check, and the descriptor recompute — every layer that
# derives ground truth from the asset.
#
# Must FAIL: refs.json pins sha256(target.smi) and Layer 0 validates it
# before any use — a tampered target is a hard fail.
set -euo pipefail
cd /workspace

# Tamper: replace the target with ethanol.
echo "CCO" > /workspace/assets/target.smi

# Run the real pipeline on the tampered target.
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

print(f"Tampered-target conformer written: E={energy:.6f} kcal/mol")
PYEOF

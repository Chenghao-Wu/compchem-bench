#!/usr/bin/env bash
# Informed cheat (asset-tampering, P2 B1 convention): the verifier's
# identity check and reference regeneration both read
# /workspace/assets/target.smi — an agent-WRITABLE path. A forger who
# overwrites it with a trivial molecule and runs the REAL pinned pipeline
# passes every recompute with zero knowledge of the original target.
#
# Must FAIL: refs.json pins sha256(target.smi) and the verifier validates it
# before any check — a tampered asset is a hard fail at Layer 0.
set -euo pipefail
mkdir -p /workspace/assets
cd /workspace

echo "CCO" > /workspace/assets/target.smi

python3 << 'PYEOF'
import json
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.ML.Cluster import Butina

with open("/workspace/assets/target.smi") as f:
    smiles = f.read().strip()

mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
params = AllChem.ETKDGv3()
params.randomSeed = 0xF00D
ids = AllChem.EmbedMultipleConfs(mol, numConfs=50, params=params)
AllChem.MMFFOptimizeMoleculeConfs(mol, mmffVariant="MMFF94", numThreads=1,
                                  maxIters=2000)
props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
energies = [float(AllChem.MMFFGetMoleculeForceField(mol, props, confId=c).CalcEnergy())
            for c in ids]
dmat = AllChem.GetConformerRMSMatrix(mol, prealigned=False)
clusters = Butina.ClusterData(dmat, len(ids), 1.0, isDistData=True,
                              reordering=True)
with open("conformers.sdf", "w") as f:
    writer = Chem.SDWriter(f)
    for c in ids:
        writer.write(mol, confId=c)
    writer.close()
results = {
    "values": {
        "n_conformers": len(ids),
        "n_clusters": len(clusters),
        "n_largest_cluster": max(len(c) for c in clusters),
        "min_mmff_energy": min(energies),
    },
    "units": {
        "n_conformers": "1",
        "n_clusters": "1",
        "n_largest_cluster": "1",
        "min_mmff_energy": "kcal/mol",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Tampered target + honest pinned pipeline on the tampered molecule")
PYEOF

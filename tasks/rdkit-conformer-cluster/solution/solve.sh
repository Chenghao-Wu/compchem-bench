#!/usr/bin/env bash
# Oracle solution for rdkit-conformer-cluster.
set -euo pipefail
cd /workspace

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
if len(ids) != 50:
    raise RuntimeError(f"expected 50 conformers, got {len(ids)}")

# MMFF94-optimize every conformer, single-threaded for determinism
results = AllChem.MMFFOptimizeMoleculeConfs(
    mol, mmffVariant="MMFF94", numThreads=1, maxIters=2000)
not_converged = [i for i, (status, _) in enumerate(results) if status != 0]
if not_converged:
    raise RuntimeError(f"MMFF optimization did not converge for conformers: "
                       f"{not_converged}")

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

results_json = {
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
    json.dump(results_json, f, indent=2)

print(f"conformers={len(ids)} clusters={len(clusters)} "
      f"largest={max(len(c) for c in clusters)} "
      f"min_E={min(energies):.6f} kcal/mol")
PYEOF

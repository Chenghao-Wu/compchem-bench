#!/usr/bin/env bash
# Informed cheat: a forger who knows RDKit but does NOT follow the pinned
# pipeline — embeds 50 conformers with a DIFFERENT seed and MMFF-optimizes
# them properly, then honestly reports the true energies and clusters of
# that ensemble (so even a verifier that only recomputes submitted
# geometries and re-clusters them would pass).
# Must FAIL at Layer 4: the verifier regenerates the reference ensemble
# from the pinned seed and matches energies conformer by conformer — a
# differently-seeded ensemble diverges immediately.
set -euo pipefail
mkdir -p /workspace
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
params.randomSeed = 42  # wrong seed
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

print(f"Forged ensemble (wrong seed, honestly reported): clusters={len(clusters)} "
      f"min_E={min(energies):.6f}")
PYEOF

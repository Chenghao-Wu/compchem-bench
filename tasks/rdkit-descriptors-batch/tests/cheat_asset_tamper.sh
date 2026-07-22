#!/usr/bin/env bash
# Informed cheat (asset-tampering, P2 B1 convention): the verifier's ground
# truth is recomputed from /workspace/assets/input_smiles.txt — an
# agent-WRITABLE path. A forger who overwrites the asset with a handful of
# trivial molecules, then computes descriptors HONESTLY on the tampered
# input, passes the full recompute with zero knowledge of the original task.
#
# Must FAIL: refs.json pins sha256(asset) and the verifier validates it
# before recomputing — a tampered asset is a hard fail at Layer 0.
set -euo pipefail
mkdir -p /workspace/assets
cd /workspace

cat > /workspace/assets/input_smiles.txt << 'EOF'
C
CC
CCC
EOF

python3 << 'PYEOF'
import csv
import json
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, Lipinski, rdMolDescriptors

with open("/workspace/assets/input_smiles.txt") as f:
    lines = [l.strip() for l in f if l.strip()]

rows = []
for s in lines:
    mol = Chem.MolFromSmiles(s)
    rows.append({
        "canonical_smiles": Chem.MolToSmiles(mol),
        "mw": Descriptors.MolWt(mol),
        "logp": Crippen.MolLogP(mol),
        "tpsa": rdMolDescriptors.CalcTPSA(mol),
        "hbd": Lipinski.NumHDonors(mol),
        "hba": Lipinski.NumHAcceptors(mol),
    })

with open("descriptors.csv", "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["canonical_smiles", "mw", "logp", "tpsa", "hbd", "hba"])
    writer.writeheader()
    writer.writerows(rows)

results = {
    "values": {"n_input": len(lines), "n_rows": len(rows)},
    "units": {"n_input": "1", "n_rows": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Tampered asset + honest computation on the tampered input")
PYEOF

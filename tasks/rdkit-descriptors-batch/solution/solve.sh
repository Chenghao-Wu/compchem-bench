#!/usr/bin/env bash
# Oracle solution for rdkit-descriptors-batch.
set -euo pipefail
cd /workspace

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
    if mol is None:
        raise RuntimeError(f"input line not parseable: {s!r}")
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

print(f"Wrote {len(rows)} descriptor rows; MW sum = "
      f"{sum(r['mw'] for r in rows):.6f}")
PYEOF

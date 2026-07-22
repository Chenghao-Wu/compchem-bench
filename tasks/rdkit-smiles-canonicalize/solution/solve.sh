#!/usr/bin/env bash
# Oracle solution for rdkit-smiles-canonicalize.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from rdkit import Chem

with open("/workspace/assets/input_smiles.txt") as f:
    lines = [l.strip() for l in f if l.strip()]

canonical = []
for s in lines:
    mol = Chem.MolFromSmiles(s)
    if mol is None:
        continue
    canonical.append(Chem.MolToSmiles(mol))

with open("canonical.smi", "w") as f:
    f.write("\n".join(canonical) + "\n")

results = {
    "values": {
        "n_input": len(lines),
        "n_valid": len(canonical),
        "n_unique": len(set(canonical)),
    },
    "units": {
        "n_input": "1",
        "n_valid": "1",
        "n_unique": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"{len(lines)} input, {len(canonical)} valid, {len(set(canonical))} unique")
PYEOF

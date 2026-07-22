#!/usr/bin/env bash
# Oracle solution for rdkit-mol-standardize.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

suppl = Chem.SDMolSupplier("/workspace/assets/messy.sdf")
chooser = rdMolStandardize.LargestFragmentChooser()
uncharger = rdMolStandardize.Uncharger()

n_input, n_parsed, n_failed = 0, 0, 0
canon = []
for mol in suppl:
    n_input += 1
    if mol is None:
        n_failed += 1
        continue
    n_parsed += 1
    frag = chooser.choose(mol)
    neu = uncharger.uncharge(frag)
    canon.append(Chem.MolToSmiles(neu))

unique = sorted(set(canon))
with open("standardized.smi", "w") as f:
    for s in unique:
        f.write(s + "\n")

results = {
    "values": {
        "n_input": n_input,
        "n_parsed": n_parsed,
        "n_failed": n_failed,
        "n_unique": len(unique),
    },
    "units": {
        "n_input": "1",
        "n_parsed": "1",
        "n_failed": "1",
        "n_unique": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"records={n_input} parsed={n_parsed} failed={n_failed} unique={len(unique)}")
PYEOF

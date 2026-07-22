#!/usr/bin/env bash
# Oracle solution for rdkit-reaction-enumerate.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import csv
import json
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.rdChemReactions import ReactionFromSmarts

MW_MIN, MW_MAX, MAX_ROT = 150.0, 350.0, 8

with open("/workspace/assets/reaction.smirks") as f:
    rxn = ReactionFromSmarts(f.read().strip())
rxn.Initialize()
assert rxn.GetNumReactantTemplates() == 2

acids, amines = [], []
with open("/workspace/assets/building_blocks.csv") as f:
    for row in csv.DictReader(f):
        mol = Chem.MolFromSmiles(row["smiles"])
        if mol is None:
            raise RuntimeError(f"unparseable building block: {row}")
        (acids if row["role"] == "acid" else amines).append(mol)

n_pairs = 0
raw = []
for acid in acids:
    for amine in amines:
        n_pairs += 1
        for product_tuple in rxn.RunReactants((acid, amine)):
            raw.extend(product_tuple)

ok, n_failed = [], 0
for p in raw:
    try:
        p.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(p)
    except Exception:
        n_failed += 1
        continue
    ok.append(p)

seen, uniq = set(), []
for p in ok:
    ik = Chem.MolToInchiKey(p)
    if ik not in seen:
        seen.add(ik)
        uniq.append(p)

kept = [p for p in uniq
        if MW_MIN <= Descriptors.MolWt(p) <= MW_MAX
        and rdMolDescriptors.CalcNumRotatableBonds(p) <= MAX_ROT]

canon = sorted(Chem.MolToSmiles(p) for p in kept)
with open("products.smi", "w") as f:
    for s in canon:
        f.write(s + "\n")

results = {
    "values": {
        "n_pairs": n_pairs,
        "n_raw_products": len(raw),
        "n_failed_sanitize": n_failed,
        "n_unique": len(uniq),
        "n_kept": len(kept),
    },
    "units": {k: "1" for k in
              ("n_pairs", "n_raw_products", "n_failed_sanitize",
               "n_unique", "n_kept")},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"pairs={n_pairs} raw={len(raw)} failed={n_failed} "
      f"unique={len(uniq)} kept={len(kept)}")
PYEOF

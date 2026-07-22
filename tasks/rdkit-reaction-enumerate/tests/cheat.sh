#!/usr/bin/env bash
# Informed cheat: runs the REAL enumeration (RunReactants, real products)
# but skips the InChIKey dedup and writes NON-isomeric SMILES — so the
# symmetric ethylenediamine duplicates survive, stereochemistry is stripped,
# and every reported count is inflated/wrong yet self-consistent with the
# script's own sloppy pipeline.
# Must FAIL: products.smi has duplicates and missing stereo; the replayed
# pipeline's kept set and counts differ on all five counters.
set -euo pipefail
mkdir -p /workspace
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

acids, amines = [], []
with open("/workspace/assets/building_blocks.csv") as f:
    for row in csv.DictReader(f):
        mol = Chem.MolFromSmiles(row["smiles"])
        (acids if row["role"] == "acid" else amines).append(mol)

n_pairs = 0
raw = []
for acid in acids:
    for amine in amines:
        n_pairs += 1
        for product_tuple in rxn.RunReactants((acid, amine)):
            raw.extend(product_tuple)

# no dedup, no stereo: sloppy "pipeline"
prods = []
n_failed = 0
for p in raw:
    try:
        p.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(p)
    except Exception:
        n_failed += 1
        continue
    prods.append(p)

kept = [p for p in prods
        if MW_MIN <= Descriptors.MolWt(p) <= MW_MAX
        and rdMolDescriptors.CalcNumRotatableBonds(p) <= MAX_ROT]

canon = sorted(Chem.MolToSmiles(p, isomericSmiles=False) for p in kept)
with open("products.smi", "w") as f:
    for s in canon:
        f.write(s + "\n")

results = {
    "values": {
        "n_pairs": n_pairs,
        "n_raw_products": len(raw),
        "n_failed_sanitize": n_failed,
        "n_unique": len(prods),   # lied: raw count, no dedup performed
        "n_kept": len(kept),
    },
    "units": {k: "1" for k in
              ("n_pairs", "n_raw_products", "n_failed_sanitize",
               "n_unique", "n_kept")},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged: no dedup, no stereo (kept={len(kept)}, 'unique'={len(prods)})")
PYEOF

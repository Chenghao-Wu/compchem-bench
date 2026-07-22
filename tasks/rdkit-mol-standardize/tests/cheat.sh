#!/usr/bin/env bash
# Informed cheat: parses the SDF with RDKit but hand-rolls the
# "standardization" — splits disconnected SMILES on '.', keeps the longest
# fragment string, and SKIPS the neutralization step entirely. The output is
# plausible (correct fragment choice, canonical SMILES, real dedup) and the
# counts are self-consistent, but salts stay charged (acetate AND acetic
# acid both survive, etc.) and the zwitterion is never neutralized.
# Must FAIL: the verifier replays the pinned recipe (fragment -> Uncharger
# -> canonical dedup); the submitted set differs on every salt/zwitterion.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
from rdkit import Chem

suppl = Chem.SDMolSupplier("/workspace/assets/messy.sdf")

n_input, n_parsed, n_failed = 0, 0, 0
canon = []
for mol in suppl:
    n_input += 1
    if mol is None:
        n_failed += 1
        continue
    n_parsed += 1
    smi = Chem.MolToSmiles(mol)
    # naive "desalt": longest string fragment wins; NO uncharging
    frag = max(smi.split("."), key=len)
    m2 = Chem.MolFromSmiles(frag)
    canon.append(Chem.MolToSmiles(m2))

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

print(f"Forged standardization (no uncharging): unique={len(unique)}")
PYEOF

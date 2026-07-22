#!/usr/bin/env bash
# Informed cheat: fixes all three crashes properly (modern rdMolStandardize
# API, sanitizing parse, None handling) — but computes the mean MW with
# CalcExactMolWt (monoisotopic mass) instead of the average MolWt the task
# asks for. The script runs cleanly, its mols.smi is correct, and the
# output is fully self-consistent — a subtle expert slip.
# Must FAIL: the verifier recomputes the average MW itself; the
# monoisotopic mean differs from the average-weight mean by far more than
# the 1e-4 tolerance.
set -euo pipefail
mkdir -p /workspace
cd /workspace

cat > analyze_mols.py << 'PYEOF'
#!/usr/bin/env python3
import json
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem import rdMolDescriptors


def normalize(mol):
    return rdMolStandardize.Cleanup(mol)


def main():
    with open("/workspace/assets/input.smi") as f:
        lines = [l.strip() for l in f if l.strip()]
    mws, canon, n_failed = [], [], 0
    for smi in lines:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            n_failed += 1
            continue
        mol = normalize(mol)
        mws.append(rdMolDescriptors.CalcExactMolWt(mol))  # monoisotopic — wrong
        canon.append(Chem.MolToSmiles(mol))
    n_parsed = len(mws)
    results = {
        "values": {
            "n_input": len(lines),
            "n_parsed": n_parsed,
            "n_failed": n_failed,
            "mw_mean": sum(mws) / n_parsed,
        },
        "units": {
            "n_input": "1",
            "n_parsed": "1",
            "n_failed": "1",
            "mw_mean": "g/mol",
        },
    }
    with open("/workspace/mols.smi", "w") as f:
        for s in canon:
            f.write(s + "\n")
    with open("/workspace/results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
PYEOF

python3 analyze_mols.py

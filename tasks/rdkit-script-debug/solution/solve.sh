#!/usr/bin/env bash
# Oracle solution for rdkit-script-debug: fix the three bugs and run the
# fixed script for real.
#   1. removed rdkit.Chem.MolStandardize.standardize.Standardizer ->
#      rdMolStandardize.Cleanup
#   2. sanitize=False without UpdatePropertyCache/SanitizeMol -> parse with
#      sanitization on (default)
#   3. no handling of unparseable lines -> skip + count None results
set -euo pipefail
cd /workspace

cat > analyze_mols.py << 'PYEOF'
#!/usr/bin/env python3
"""analyze_mols.py — read a SMILES list, normalize each molecule, and
report per-molecule canonical SMILES plus MW statistics. (fixed)"""
import json

from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize


def normalize(mol):
    """Normalize functional-group representations (e.g. nitro groups)."""
    return rdMolStandardize.Cleanup(mol)


def main():
    with open("/workspace/assets/input.smi") as f:
        lines = [l.strip() for l in f if l.strip()]

    mws = []
    canon = []
    n_failed = 0
    for smi in lines:
        mol = Chem.MolFromSmiles(smi)  # sanitize on; None if unparseable
        if mol is None:
            n_failed += 1
            continue
        mol = normalize(mol)
        mws.append(Descriptors.MolWt(mol))
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
    print(f"parsed {n_parsed}/{len(lines)} molecules, "
          f"mean MW {results['values']['mw_mean']:.4f} g/mol")


if __name__ == "__main__":
    main()
PYEOF

python3 analyze_mols.py

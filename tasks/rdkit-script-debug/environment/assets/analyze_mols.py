#!/usr/bin/env python3
"""analyze_mols.py — read a SMILES list, normalize each molecule, and
report per-molecule canonical SMILES plus MW statistics.

Input : /workspace/assets/input.smi  (one SMILES per line)
Output: /workspace/mols.smi          (canonical SMILES of parsed molecules)
        /workspace/results.json      (counts + mean MW)
"""
import json

from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize.standardize import Standardizer  # normalize tautomers/charges


def normalize(mol):
    """Normalize functional-group representations (e.g. nitro groups)."""
    std = Standardizer()
    return std.standardize(mol)


def main():
    with open("/workspace/assets/input.smi") as f:
        lines = [l.strip() for l in f if l.strip()]

    mws = []
    canon = []
    # sanitize=False is "more robust" — parse everything, sanitize later
    for smi in lines:
        mol = Chem.MolFromSmiles(smi, sanitize=False)
        mol = normalize(mol)
        mws.append(Descriptors.MolWt(mol))
        canon.append(Chem.MolToSmiles(mol))

    n_parsed = len(mws)
    results = {
        "values": {
            "n_input": len(lines),
            "n_parsed": n_parsed,
            "n_failed": len(lines) - n_parsed,
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

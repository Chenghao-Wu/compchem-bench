#!/usr/bin/env bash
# Informed cheat (asset-tampering, P2 B1 convention): both the agent's
# script and the verifier's recompute read /workspace/assets/input.smi — an
# agent-WRITABLE path. A forger who overwrites the input with three trivial
# molecules and runs a properly fixed script passes the rerun AND the
# recompute with zero knowledge of the original input.
#
# Must FAIL: refs.json pins sha256(input.smi) and the verifier validates it
# before rerunning — a tampered asset is a hard fail at Layer 0.
set -euo pipefail
mkdir -p /workspace/assets
cd /workspace

cat > /workspace/assets/input.smi << 'EOF'
C
CC
CCC
EOF

cat > analyze_mols.py << 'PYEOF'
#!/usr/bin/env python3
import json
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize


def main():
    with open("/workspace/assets/input.smi") as f:
        lines = [l.strip() for l in f if l.strip()]
    mws, canon, n_failed = [], [], 0
    for smi in lines:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            n_failed += 1
            continue
        mol = rdMolStandardize.Cleanup(mol)
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


if __name__ == "__main__":
    main()
PYEOF

python3 analyze_mols.py
echo "Tampered input + honest fixed script"

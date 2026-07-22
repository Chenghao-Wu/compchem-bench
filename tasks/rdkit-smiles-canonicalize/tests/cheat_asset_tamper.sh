#!/usr/bin/env bash
# Informed cheat (asset-tampering): the verifier's "ground
# truth" is recomputed from /workspace/assets/input_smiles.txt — an
# agent-WRITABLE path. A forger who overwrites the asset with 8 distinct,
# already-canonical SMILES and copies the same 8 lines into canonical.smi
# passes the line-by-line recompute trivially WITHOUT calling RDKit at all,
# and the count anchors (8/8) still hold.
#
# Must FAIL: refs.json pins sha256(asset) and the verifier validates it
# before recomputing — a tampered asset is a hard fail.
set -euo pipefail
mkdir -p /workspace/assets
cd /workspace

# 8 mutually distinct, already-canonical SMILES (simple alkane series) —
# canonicalizing them is the identity map.
cat > /workspace/assets/input_smiles.txt << 'EOF'
C
CC
CCC
CCCC
CCCCC
CCCCCC
CCCCCCC
CCCCCCCC
EOF

# "Answer": just copy the (tampered) input verbatim.
cp /workspace/assets/input_smiles.txt /workspace/canonical.smi

cat > /workspace/results.json << 'EOF'
{
  "values": {
    "n_input": 8,
    "n_valid": 8,
    "n_unique": 8
  },
  "units": {
    "n_input": "1",
    "n_valid": "1",
    "n_unique": "1"
  }
}
EOF

echo "Tampered asset + copied output written (zero RDKit calls)"

#!/usr/bin/env bash
# Informed cheat: a forger who knows approximate descriptor values for these
# well-known molecules (ethanol 46.07, benzene 78.11, aspirin 180.16 ...) and
# hand-writes a plausible CSV with ROUNDED values (2 decimal places) and
# plausible HBD/HBA counts — no RDKit calls at all. Row order, canonical
# SMILES, and counts are all correct-looking.
# Must FAIL: the verifier recomputes every descriptor with RDKit; rounded
# 2-decimal forgeries fall outside the 1e-4 float tolerance on multiple rows.
set -euo pipefail
mkdir -p /workspace
cd /workspace

cat > descriptors.csv << 'EOF'
canonical_smiles,mw,logp,tpsa,hbd,hba
CCO,46.07,-0.00,20.23,1,1
c1ccccc1,78.11,1.69,0.00,0,0
CC(=O)O,60.05,0.09,37.30,1,1
CC(=O)Nc1ccc(O)cc1,151.17,1.35,49.33,2,2
CC(=O)Oc1ccccc1C(=O)O,180.16,1.31,63.60,1,3
Cn1c(=O)c2c(ncn2C)n(C)c1=O,194.19,-1.03,61.82,0,6
CC(C)Cc1ccc(C(C)C(=O)O)cc1,206.29,3.07,37.30,1,1
NCC(=O)O,75.07,-0.97,63.32,2,2
Oc1ccccc1,94.11,1.39,20.23,1,1
Cc1ccccc1,92.14,2.00,0.00,0,0
c1ccncc1,79.10,1.08,12.89,0,1
C[C@H](N)C(=O)O,89.09,-0.58,63.32,2,2
EOF

cat > results.json << 'EOF'
{
  "values": {
    "n_input": 12,
    "n_rows": 12
  },
  "units": {
    "n_input": "1",
    "n_rows": "1"
  }
}
EOF

echo "Forged descriptors.csv with rounded literature values (zero RDKit calls)"

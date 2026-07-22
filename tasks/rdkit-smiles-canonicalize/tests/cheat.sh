#!/usr/bin/env bash
# Informed cheat: a forger who knows SMILES syntax and produces plausible-
# looking "canonical" forms by hand (stripping parentheses, naive atom
# reordering, lowercasing aromatics) without calling RDKit. The output is
# superficially reasonable and self-consistent, but it is NOT RDKit's
# canonicalization.
# Must FAIL: the verifier recomputes RDKit canonical SMILES for every
# input line and compares exactly.
mkdir -p /workspace
cat > /workspace/canonical.smi << 'EOF'
c1ccccc1CO
CC(C)O
Oc1ccccc1
CC(=O)Oc1ccccc1C(=O)O
C[C@@H](N)C(=O)O
OC[C@H](O)CO
c1ccccc1
[Na+].[Cl-]
EOF
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

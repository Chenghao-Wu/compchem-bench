#!/usr/bin/env bash
# Informed-cheat baseline: produces a plausible, self-consistent forgery
# of results.json WITHOUT running real calculations. CI gate requires
# this script to FAIL — it proves the verifier catches forgery.
set -euo pipefail

echo "Cheat: fabricating plausible-but-wrong results.json"

cat > /workspace/results.json << 'EOF'
{
  "values": {
    "dpa3_mol_energy_eV": -8000.000000000000,
    "mattersim_mol_energy_eV": -60.000000000000,
    "dpa3_surf_energy_eV": -300.000000000000,
    "mattersim_surf_energy_eV": -300.000000000000
  },
  "units": {
    "dpa3_mol_energy_eV": "eV",
    "mattersim_mol_energy_eV": "eV",
    "dpa3_surf_energy_eV": "eV",
    "mattersim_surf_energy_eV": "eV"
  }
}
EOF

# Also produce a fake but internally-consistent native output
echo "Cheat: done (fabricated results.json)"

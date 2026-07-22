#!/usr/bin/env bash
# Oracle solution for xtb-singlepoint-gfn2.
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1
xtb /workspace/assets/acetonitrile.xyz --gfn 2 > xtb_sp.out 2>&1

python3 << 'PYEOF'
import json
import re

with open("xtb_sp.out") as f:
    content = f.read()

m = re.findall(r"TOTAL ENERGY\s+([-\d.]+)\s+Eh", content)
if not m:
    raise RuntimeError("No TOTAL ENERGY line found")
total_energy = float(m[-1])

m = re.findall(r"HOMO-LUMO GAP\s+([-\d.]+)\s+eV", content)
if not m:
    raise RuntimeError("No HOMO-LUMO GAP line found")
gap = float(m[-1])

results = {
    "values": {
        "total_energy": total_energy,
        "homo_lumo_gap": gap,
    },
    "units": {
        "total_energy": "Eh",
        "homo_lumo_gap": "eV",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={total_energy:.10f} Eh, gap={gap:.6f} eV")
PYEOF

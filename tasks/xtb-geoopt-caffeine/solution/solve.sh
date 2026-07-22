#!/usr/bin/env bash
# Oracle solution for xtb-geoopt-caffeine.
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1
xtb /workspace/assets/caffeine.xyz --gfn 2 --opt > xtb_opt.out 2>&1

python3 << 'PYEOF'
import json
import re

with open("xtb_opt.out") as f:
    content = f.read()

m = re.findall(r"TOTAL ENERGY\s+([-\d.]+)\s+Eh", content)
if not m:
    raise RuntimeError("No TOTAL ENERGY line found")
final_energy = float(m[-1])

# molecular dipole block:
#   molecular dipole:
#                    x           y           z       tot (Debye)
#    q only: ...
#      full:        1.378      -0.791      -0.172       4.063
dip = re.search(r"molecular dipole:.*?full:\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)",
                content, re.DOTALL)
if not dip:
    raise RuntimeError("No molecular dipole block found")
dipole = float(dip.group(1))

converged = "GEOMETRY OPTIMIZATION CONVERGED" in content

results = {
    "values": {
        "final_energy": final_energy,
        "dipole_moment": dipole,
        "opt_converged": converged,
    },
    "units": {
        "final_energy": "Eh",
        "dipole_moment": "Debye",
        "opt_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={final_energy:.10f} Eh, dipole={dipole:.4f} Debye, converged={converged}")
PYEOF

#!/usr/bin/env bash
# Oracle solution for qe-output-parse.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import re

with open("/workspace/assets/sample_run/si_sample.out") as f:
    content = f.read()

energy = float(re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)[-1])
force = float(re.search(r"Total force =\s+([-\d.]+)", content).group(1))
fermi = float(re.search(r"the Fermi energy is\s+([-\d.]+)\s+ev", content).group(1))

results = {
    "values": {
        "final_energy": energy,
        "total_force": force,
        "fermi_energy": fermi,
    },
    "units": {
        "final_energy": "Ry",
        "total_force": "Ry/bohr",
        "fermi_energy": "eV",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={energy:.8f} Ry, F_total={force:.6f} Ry/bohr, E_F={fermi:.4f} eV")
PYEOF

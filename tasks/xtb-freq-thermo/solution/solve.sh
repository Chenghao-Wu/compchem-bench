#!/usr/bin/env bash
# Oracle solution for xtb-freq-thermo.
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1
xtb /workspace/assets/ethanol.xyz --gfn 2 --ohess > xtb_thermo.out 2>&1

python3 << 'PYEOF'
import json
import re

with open("xtb_thermo.out") as f:
    content = f.read()

def grab(pattern, name):
    m = re.findall(pattern, content)
    if not m:
        raise RuntimeError(f"No {name} found")
    return float(m[-1])

total_energy = grab(r"::\s*total energy\s+([-\d.]+)\s+Eh", "total energy")
zpe = grab(r"::\s*zero point energy\s+([-\d.]+)\s+Eh", "zero point energy")
free_energy = grab(r"::\s*total free energy\s+([-\d.]+)\s+Eh", "total free energy")

m = re.findall(r"# imaginary freq\.\s+(\d+)", content)
if not m:
    raise RuntimeError("No imaginary-frequency count found")
n_imag = int(m[-1])

if "GEOMETRY OPTIMIZATION CONVERGED" not in content:
    raise RuntimeError("Optimization did not converge")
if n_imag != 0:
    raise RuntimeError(f"Found {n_imag} imaginary frequencies")

results = {
    "values": {
        "total_energy": total_energy,
        "zpe": zpe,
        "free_energy_298": free_energy,
        "n_imaginary_freqs": n_imag,
    },
    "units": {
        "total_energy": "Eh",
        "zpe": "Eh",
        "free_energy_298": "Eh",
        "n_imaginary_freqs": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={total_energy:.10f} Eh, ZPE={zpe:.10f} Eh, "
      f"G(298)={free_energy:.10f} Eh, n_imag={n_imag}")
PYEOF

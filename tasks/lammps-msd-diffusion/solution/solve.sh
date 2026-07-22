#!/usr/bin/env bash
# Oracle solution for lammps-msd-diffusion.
set -euo pipefail
cd /workspace

cp /workspace/assets/msd.in ./msd.in

export OMP_NUM_THREADS=1
lmp_serial -in msd.in

python3 << 'PYEOF'
import json
import re

import numpy as np

DT = 0.005
PROD_START = 2000
FIT_FROM = 7000

with open("log.lammps") as f:
    log = f.read()

# Collect thermo segments; the production segment has 4 columns
# (step temp pe msd) and starts at step 2000.
segments = []
cur = None
for line in log.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        cur = []
        segments.append(cur)
        continue
    if cur is not None and re.match(r"^\d+\s+[-\d.eE+]+", s):
        cur.append(s)
    if "Loop time" in line:
        cur = None

prod = segments[-1]
steps = np.array([float(l.split()[0]) for l in prod])
msd = np.array([float(l.split()[3]) for l in prod])

mask = steps >= FIT_FROM
t = (steps[mask] - PROD_START) * DT
slope, intercept = np.polyfit(t, msd[mask], 1)
D = slope / 6.0

results = {
    "values": {"diffusion_D": D, "n_msd_rows": len(prod)},
    "units": {"diffusion_D": "σ²/τ", "n_msd_rows": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"D = {D:.5f} σ²/τ from {mask.sum()} rows (steps>={FIT_FROM})")
PYEOF

#!/usr/bin/env bash
# Oracle solution for lammps-restart-continue.
set -euo pipefail
cd /workspace

cat > continue.in << 'EOF'
# Continue the NVT-equilibrated LJ fluid in NVE.
# read_restart restores box, atoms, velocities, masses, and pair settings.
read_restart     /workspace/assets/equil.restart

neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no

thermo          100
thermo_style    custom step temp pe

fix             1 all nve
run             2000

write_data      final.data
EOF

export OMP_NUM_THREADS=1
lmp_serial -in continue.in

python3 << 'PYEOF'
import json
import re

with open("log.lammps") as f:
    log = f.read()

thermo = []
in_run = False
for line in log.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[-\d.eE+]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

if len(thermo) != 21:
    raise RuntimeError(f"Expected 21 thermo lines, got {len(thermo)}")

first = thermo[0].split()
last = thermo[-1].split()
results = {
    "values": {
        "first_step": int(first[0]),
        "first_pe": float(first[2]),
        "final_step": int(last[0]),
        "final_pe": float(last[2]),
        "final_temp": float(last[1]),
    },
    "units": {
        "first_step": "1",
        "first_pe": "ε/atom",
        "final_step": "1",
        "final_pe": "ε/atom",
        "final_temp": "ε/kB",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"first step {first[0]} PE {first[2]} -> final step {last[0]} PE {last[2]} T {last[1]}")
PYEOF

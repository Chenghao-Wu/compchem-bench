#!/usr/bin/env bash
# Oracle solution for lammps-lj-melt.
set -euo pipefail
cd /workspace

cp /workspace/assets/lj_melt.in ./lj_melt.in
lmp_serial -in lj_melt.in

python3 << 'PYEOF'
import json
import re

with open("log.lammps") as f:
    lines = f.readlines()

log_lines = len(lines)

# Find thermo output lines (lines starting with integer step numbers in thermo block)
thermo_lines = []
in_run = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("Step ") or stripped.startswith("step "):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[\d.eE+\-]+", stripped):
        thermo_lines.append(stripped)
    if "Loop time" in line:
        in_run = False

if not thermo_lines:
    raise RuntimeError("No thermo data found in log.lammps")

last = thermo_lines[-1].split()
results = {
    "values": {
        "final_step": int(last[0]),
        "final_temp": float(last[1]),
        "final_pe": float(last[2]),
        "log_lines": log_lines,
    },
    "units": {
        "final_step": "1",
        "final_temp": "ε/kB",
        "final_pe": "ε/atom",
        "log_lines": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"step={results['values']['final_step']} T={results['values']['final_temp']:.4f} "
      f"PE={results['values']['final_pe']:.4f}")
PYEOF

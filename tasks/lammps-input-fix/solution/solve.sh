#!/usr/bin/env bash
# Oracle solution for lammps-input-fix.
set -euo pipefail
cd /workspace

# The three errors in broken.in:
#   1. "pair_styl"    -> "pair_style"
#   2. missing        -> "mass 1 1.0"
#   3. "thermo_styl"  -> "thermo_style"
cp /workspace/assets/broken.in ./fixed.in
sed -i 's/^pair_styl/pair_style/' fixed.in
sed -i 's/^thermo_styl/thermo_style/' fixed.in
sed -i '/^create_atoms/a\
\
mass            1 1.0' fixed.in

export OMP_NUM_THREADS=1
lmp_serial -in fixed.in

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
    if in_run and re.match(r"^\d+\s+[\d.eE+\-]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

if not thermo:
    raise RuntimeError("No thermo data in log.lammps")

last = thermo[-1].split()
results = {
    "values": {
        "final_step": int(last[0]),
        "final_temp": float(last[1]),
        "final_pe": float(last[2]),
    },
    "units": {
        "final_step": "1",
        "final_temp": "ε/kB",
        "final_pe": "ε/atom",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"step={results['values']['final_step']} T={results['values']['final_temp']:.4f} "
      f"PE={results['values']['final_pe']:.4f}")
PYEOF

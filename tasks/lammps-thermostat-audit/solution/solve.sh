#!/usr/bin/env bash
# Oracle solution for lammps-thermostat-audit.
#
# Diagnosis of broken.in:
#   1. The Nose-Hoover thermostat is applied to group "mobile" (type 1
#      only) — half the fluid is unthermostatted, so the system is not
#      sampled as one NVT ensemble.
#   2. timestep 0.015 is too large for an LJ fluid at T*~1.2 (standard
#      choice is ~0.005), giving poor integration of the untemostatted half.
set -euo pipefail
cd /workspace

cat > fixed.in << 'EOF'
units           lj
atom_style      atomic
dimension       3
boundary        p p p

lattice         fcc 0.8442
region          box block 0 5 0 5 0 5
create_box      2 box
create_atoms    1 box
set             group all type/fraction 2 0.5 48293

mass            1 1.0
mass            2 1.0

pair_style      lj/cut 2.5
pair_coeff      1 1 1.0 1.0 2.5
pair_coeff      1 2 1.0 1.0 2.5
pair_coeff      2 2 1.0 1.0 2.5

neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no

velocity        all create 1.2 2718 loop geom

# FIX 2: sane timestep
timestep        0.005

thermo          100
thermo_style    custom step temp pe etotal

# FIX 1: thermostat the WHOLE fluid
fix             1 all nvt temp 1.2 1.2 0.5

dump            d all custom 100 state.dump id type x y z vx vy vz

run             5000
EOF

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
    if in_run and re.match(r"^\d+\s+[-\d.eE+]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

temps = [float(l.split()[1]) for l in thermo if int(l.split()[0]) >= 2500]
avg_temp = sum(temps) / len(temps)

results = {
    "values": {"avg_temp": avg_temp, "final_step": int(thermo[-1].split()[0])},
    "units": {"avg_temp": "ε/kB", "final_step": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"avg_temp (steps>=2500) = {avg_temp:.5f}, final_step = {thermo[-1].split()[0]}")
PYEOF

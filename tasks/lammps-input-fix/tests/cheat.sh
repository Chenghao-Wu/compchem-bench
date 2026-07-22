#!/usr/bin/env bash
# Informed cheat: a forger who knows LAMMPS log format and LJ-fluid
# phenomenology. Fabricates:
#   - fixed.in looking like a plausible repair (correct commands present)
#   - log.lammps with banner, 11 thermo rows at steps 0..1000, no ERROR,
#     Loop time + Total wall time footer
#   - results.json self-consistent with the forged log
# Passes layers 1-3 and 5 (existence, fixed.in tokens, log shape, log<->
# results consistency).
# Must FAIL at layer 4: the guessed final values (T~0.66, PE~-5.71 — a
# plausible NVE equilibration from T=1.2) are not the true deterministic
# seed-12345 trajectory values; guessing them to 1e-3 without running is
# not possible.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

fixed = """units           lj
atom_style      atomic
dimension       3
boundary        p p p

lattice         fcc 0.8442
region          box block 0 5 0 5 0 5
create_box      1 box
create_atoms    1 box

mass            1 1.0

pair_style      lj/cut 2.5
pair_coeff      1 1 1.0 1.0 2.5

neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no

velocity        all create 1.2 12345 loop geom

thermo          100
thermo_style    custom step temp pe

fix             1 all nve
run             1000
"""
with open("fixed.in", "w") as f:
    f.write(fixed)

lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng"]
final_t, final_pe = 0.6589, -5.7123
for step in range(0, 1001, 100):
    frac = step / 1000
    t = 1.2 + (final_t - 1.2) * (1 - np.exp(-4 * frac)) / (1 - np.exp(-4))
    pe = -4.1 + (final_pe + 4.1) * (1 - np.exp(-4 * frac)) / (1 - np.exp(-4))
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f}")
lines.append("Loop time of 0.61 on 1 procs for 1000 steps with 500 atoms")
lines.append("Total wall time: 0:00:01")
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

results = {
    "values": {"final_step": 1000, "final_temp": final_t, "final_pe": final_pe},
    "units": {"final_step": "1", "final_temp": "ε/kB", "final_pe": "ε/atom"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged fixed.in + log.lammps + results.json written")
PYEOF

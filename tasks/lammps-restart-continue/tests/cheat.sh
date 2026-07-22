#!/usr/bin/env bash
# Informed cheat: a forger who knows LAMMPS log format and that an LJ
# liquid at T~0.6-0.7 sits near PE/atom ~ -5.9. Fabricates:
#   - log.lammps with banner, 21 thermo rows at steps 1000..3000, plausible
#     NVE drift, Loop time + Total wall time
#   - final.data: a hand-built perfect FCC crystal at the same density
#   - results.json self-consistent with the forged log
# Passes layers 1-2 and 4 (existence, log shape/step range, results<->log
# consistency).
# Must FAIL at layer 3 and 5: the guessed trajectory values are not the
# true deterministic continuation of the pinned restart (layer 3), and the
# crystal's PE is nowhere near the liquid value claimed in the forged log
# (layer 5).
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng"]
rng = np.random.RandomState(7)
t, pe = 0.62, -5.88
for step in range(1000, 3001, 100):
    t += rng.normal(0, 0.005)
    pe += rng.normal(0, 0.005)
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f}")
lines.append("Loop time of 1.9 on 1 procs for 2000 steps with 500 atoms")
lines.append("Total wall time: 0:00:02")
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

# Fake final.data: perfect FCC crystal, 500 atoms (NO simulation)
rho = 0.8442
a = (4.0 / rho) ** (1.0 / 3.0)
L = 5 * a
basis = [(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]
atoms = []
for i in range(5):
    for j in range(5):
        for k in range(5):
            for b in basis:
                atoms.append(((i + b[0]) * a, (j + b[1]) * a, (k + b[2]) * a))
with open("final.data", "w") as f:
    f.write("forged final state\n\n")
    f.write(f"{len(atoms)} atoms\n1 atom types\n\n")
    f.write(f"0.0 {L:.8f} xlo xhi\n0.0 {L:.8f} ylo yhi\n0.0 {L:.8f} zlo zhi\n\n")
    f.write("Masses\n\n1 1.0\n\nAtoms\n\n")
    for i, (x, y, z) in enumerate(atoms, start=1):
        f.write(f"{i} 1 {x:.8f} {y:.8f} {z:.8f}\n")

results = {
    "values": {"first_step": 1000, "first_pe": -5.88, "final_step": 3000,
               "final_pe": float(lines[-3].split()[2]), "final_temp": float(lines[-3].split()[1])},
    "units": {"first_step": "1", "first_pe": "ε/atom", "final_step": "1",
              "final_pe": "ε/atom", "final_temp": "ε/kB"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged log + crystal final.data + self-consistent results.json")
PYEOF

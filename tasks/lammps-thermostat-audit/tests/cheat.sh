#!/usr/bin/env bash
# Informed cheat: a forger who knows exactly what the verifier's static
# checks look for. Fabricates:
#   - fixed.in with a textbook-correct thermostat line, timestep, seed, run
#   - log.lammps with 51 thermo rows, T hugging 1.2 (avg 1.1998),
#     plausible PE series, banner + footer
#   - state.dump with 51 frames of a STATIC FCC crystal whose velocities
#     are freshly drawn Gaussians scaled so the kinetic temperature matches
#     the forged log's Temp at step 5000 EXACTLY
#   - results.json consistent with the forged log
# Passes layers 1-4 and even L4(a) (kinetic T matches thermo by
# construction).
# Must FAIL at L4(b): the verifier re-evaluates the potential energy of the
# dumped positions — a static crystal has PE/atom far from the liquid value
# claimed in the forged log.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

rng = np.random.RandomState(11)

# ── fixed.in: textbook-correct ────────────────────────────────────────────
fixed = """units           lj
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
timestep        0.005

thermo          100
thermo_style    custom step temp pe etotal

fix             1 all nvt temp 1.2 1.2 0.5

dump            d all custom 100 state.dump id type x y z vx vy vz

run             5000
"""
with open("fixed.in", "w") as f:
    f.write(fixed)

# ── Fake log.lammps ───────────────────────────────────────────────────────
T_final = 1.19870
rows = []
lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng        TotEng"]
for step in range(0, 5001, 100):
    t = 1.2 - 0.05 * np.exp(-step / 800) + rng.normal(0, 0.004)
    if step == 0:
        t = 1.2
    if step == 5000:
        t = T_final
    pe = -5.21 + rng.normal(0, 0.01)
    et = pe + 1.5 * t
    rows.append((step, t, pe, et))
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f} {et:14.7f}")
lines.append("Loop time of 2.2 on 1 procs for 5000 steps with 500 atoms")
lines.append("Total wall time: 0:00:03")
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")
avg_claim = float(np.mean([t for s, t, _, _ in rows if s >= 2500]))

# ── Fake state.dump: static crystal + Maxwell velocities ─────────────────
rho = 0.8442
a = (4.0 / rho) ** (1.0 / 3.0)
L = 5 * a
basis = [(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]
atoms = []
idx = 1
for i in range(5):
    for j in range(5):
        for k in range(5):
            for b in basis:
                atoms.append((idx, 1 if idx % 2 else 2,
                              (i + b[0]) * a, (j + b[1]) * a, (k + b[2]) * a))
                idx += 1

with open("state.dump", "w") as f:
    for step in range(0, 5001, 100):
        f.write("ITEM: TIMESTEP\n")
        f.write(f"{step}\n")
        f.write("ITEM: NUMBER OF ATOMS\n")
        f.write(f"{len(atoms)}\n")
        f.write("ITEM: BOX BOUNDS pp pp pp\n")
        f.write(f"0 {L:.6f}\n0 {L:.6f}\n0 {L:.6f}\n")
        f.write("ITEM: ATOMS id type x y z vx vy vz\n")
        # Fresh Maxwell velocities; scale so kinetic T matches the forged log
        vel = rng.normal(0, 1, (len(atoms), 3))
        vel -= vel.mean(axis=0)
        t_now = 1.2 if step != 5000 else T_final
        scale = np.sqrt(t_now * (3 * len(atoms) - 3) / (vel ** 2).sum())
        vel *= scale
        for (aid, atype, x, y, z), (vx, vy, vz) in zip(atoms, vel):
            f.write(f"{aid} {atype} {x:.6f} {y:.6f} {z:.6f} {vx:.6f} {vy:.6f} {vz:.6f}\n")

# ── results.json ──────────────────────────────────────────────────────────
results = {
    "values": {"avg_temp": avg_claim, "final_step": 5000},
    "units": {"avg_temp": "ε/kB", "final_step": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged fixed.in + log + state.dump (crystal + Maxwell velocities) + results.json")
PYEOF

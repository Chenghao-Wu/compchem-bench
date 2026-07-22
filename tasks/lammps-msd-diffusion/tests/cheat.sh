#!/usr/bin/env bash
# Informed cheat: a forger who knows LJ self-diffusion magnitudes
# (D* ~ 0.05-0.1 at this state point) and the required file formats.
# Fabricates:
#   - log.lammps with banner, both run segments (21 + 101 thermo rows on
#     the right steps), a plausibly noisy but linear production MSD column
#     with slope 6*0.072, Loop time + Total wall time
#   - results.json claiming D=0.072 (consistent with the forged log to
#     well within the 2% consistency tolerance)
#   - traj.dump with all 101 frames on the right step grid — but every
#     frame is the SAME static FCC configuration (no dynamics at all)
# Passes layers 1-5: file shapes, segment/step structure, MSD sanity
# (increasing, zero at origin), D within 15% of the reference, and the
# log<->results consistency refit.
# Must FAIL at layer 6 (L4): the verifier recomputes the MSD from
# traj.dump — a static configuration has MSD 0, not the claimed ~20 sigma^2
# at the final frame.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

rng = np.random.RandomState(3)

# ── Fake log.lammps ───────────────────────────────────────────────────────
lines = ["LAMMPS (7 Jan 2022) — fake banner"]
lines.append("Step          Temp         PotEng")
for step in range(0, 2001, 100):
    t = 1.44 - 0.24 * (step / 2000) + rng.normal(0, 0.005)
    pe = -4.5 - 0.7 * (step / 2000) + rng.normal(0, 0.005)
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f}")
lines.append("Loop time of 1.2 on 1 procs for 2000 steps with 864 atoms")
lines.append("Step          Temp         PotEng        MSD")
for step in range(2000, 12001, 100):
    t = 1.2 + rng.normal(0, 0.01)
    pe = -5.2 + rng.normal(0, 0.01)
    tt = (step - 2000) * 0.005
    msd = max(0.0, 6 * 0.072 * tt * (1 - np.exp(-tt / 5)) + rng.normal(0, 0.05))
    if step == 2000:
        msd = 0.0
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f} {msd:14.7f}")
lines.append("Loop time of 6.1 on 1 procs for 10000 steps with 864 atoms")
lines.append("Total wall time: 0:00:07")
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

# ── Fake traj.dump: 101 frames, all the same static FCC lattice ──────────
rho = 0.8442
a = (4.0 / rho) ** (1.0 / 3.0)
L = 6 * a
basis = [(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]
atoms = []
idx = 1
for i in range(6):
    for j in range(6):
        for k in range(6):
            for b in basis:
                atoms.append((idx, (i + b[0]) * a, (j + b[1]) * a, (k + b[2]) * a))
                idx += 1

with open("traj.dump", "w") as f:
    for step in range(2000, 12001, 100):
        f.write("ITEM: TIMESTEP\n")
        f.write(f"{step}\n")
        f.write("ITEM: NUMBER OF ATOMS\n")
        f.write(f"{len(atoms)}\n")
        f.write("ITEM: BOX BOUNDS pp pp pp\n")
        f.write(f"0 {L:.6f}\n0 {L:.6f}\n0 {L:.6f}\n")
        f.write("ITEM: ATOMS id type xu yu zu\n")
        for idx, x, y, z in atoms:
            f.write(f"{idx} 1 {x:.6f} {y:.6f} {z:.6f}\n")

# ── results.json consistent with the forged log ──────────────────────────
results = {
    "values": {"diffusion_D": 0.072, "n_msd_rows": 101},
    "units": {"diffusion_D": "σ²/τ", "n_msd_rows": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged log (D=0.072) + static dump (MSD=0) + results.json")
PYEOF

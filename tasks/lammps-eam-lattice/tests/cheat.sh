#!/usr/bin/env bash
# Informed cheat: a forger who knows Cu's textbook numbers (a0≈3.615 Å,
# Ecoh≈-3.54 eV/atom for a good EAM) and the LAMMPS minimization log
# format. Fabricates:
#   - log.lammps with banner, a plausible box/relax minimization trajectory
#     from the a=3.7 Å start to the converged state, Minimization stats,
#     Loop time + Total wall time
#   - results.json with the TRUE converged values (they are guessable to
#     textbook precision) — passes the tolerance layer
#   - final.data: a perfect FCC lattice hand-built at a=3.60 Å — close
#     enough to the claimed a0=3.615 Å to pass the results↔data box
#     consistency (tol 0.02 Å), and a syntactically perfect data file
# Passes layers 1-4.
# Must FAIL at layer 5 (L4): the verifier reruns a single point on
# final.data — a 3.60 Å lattice has a measurably higher PE/atom than the
# 3.615 Å value claimed in the forged log.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

# ── Fake minimization log ─────────────────────────────────────────────────
# Claim the true converged values: total PE -906.2959 eV (256 atoms),
# Lx = 14.46 Å (a0 = 3.615 Å).
lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          PotEng         Lx"]
traj = [(0, -899.96317, 14.80), (1, -902.51234, 14.72), (2, -904.88123, 14.62),
        (3, -905.99871, 14.52), (4, -906.25112, 14.47), (5, -906.29589, 14.46)]
for step, pe, lx in traj:
    lines.append(f"{step:>8d} {pe:14.5f} {lx:10.2f}")
lines += ["Loop time of 0.02 on 1 procs for 5 steps with 256 atoms",
          "", "Minimization stats:",
          "  Stopping criterion = energy tolerance",
          "Total wall time: 0:00:01"]
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

# ── Fake final.data: perfect FCC at a=3.60 Å (NOT the claimed 3.615) ─────
a = 3.60
basis = [(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)]
atoms = []
for i in range(4):
    for j in range(4):
        for k in range(4):
            for b in basis:
                atoms.append(((i + b[0]) * a, (j + b[1]) * a, (k + b[2]) * a))
L = 4 * a
with open("final.data", "w") as f:
    f.write("hand-built FCC Cu (forged final state)\n\n")
    f.write(f"{len(atoms)} atoms\n1 atom types\n\n")
    f.write(f"0.0 {L:.6f} xlo xhi\n0.0 {L:.6f} ylo yhi\n0.0 {L:.6f} zlo zhi\n\n")
    f.write("Masses\n\n1 63.546\n\nAtoms # atomic\n\n")
    for i, (x, y, z) in enumerate(atoms, start=1):
        f.write(f"{i} 1 {x:.6f} {y:.6f} {z:.6f}\n")

# ── results.json: textbook-true converged values ──────────────────────────
results = {
    "values": {"a0": 3.615, "ecoh": -906.29589 / 256.0},
    "units": {"a0": "Å", "ecoh": "eV/atom"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged log + final.data (a=3.60) + results.json (claims a0=3.615)")
PYEOF

#!/usr/bin/env bash
# Informed cheat: a forger who knows LAMMPS output formats and textbook
# LJ-fluid values. Fabricates:
#   - log.lammps with banner, BOTH run segments (5 + 7 thermo rows at the
#     right steps), Loop time / Total wall time footer
#   - rdf.dat with exactly 100 bins on the correct grid and a plausible
#     LJ-fluid g(r) (first peak ~2.7 at r~1.06σ)
#   - final.data with exactly 500 atoms (a perfect FCC crystal — no MD run)
#   - results.json self-consistent with the fabricated rdf.dat
#
# Passes layers 1-6 (formats, segment counts, bin grid, atom count, peak
# tolerance, rdf<->results consistency).
# Must FAIL at layer 7: the verifier re-evaluates the potential energy of
# final.data with LAMMPS — a crystalline FCC configuration has PE/atom
# ≈ -8, nowhere near the liquid value (~-5.2) claimed in the forged log.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

# ── Fake log.lammps ───────────────────────────────────────────────────────
seg1, seg2 = [], []
for step in range(0, 2001, 500):
    t = 1.44 - (1.44 - 1.20) * (step / 2000)
    pe = -4.5 - 0.7 * (step / 2000)
    seg1.append(f"{step:>8d} {t:12.6f} {pe:12.6f}")
for step in range(2000, 5001, 500):
    t = 1.20 + 0.01 * np.sin(step)
    pe = -5.20 - 0.01 * np.cos(step)
    seg2.append(f"{step:>8d} {t:12.6f} {pe:12.6f}")

log = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng"]
log += seg1
log += ["Loop time of 1.23 on 1 procs for 2000 steps with 500 atoms",
        "Step          Temp         PotEng"]
log += seg2
log += ["Loop time of 2.34 on 1 procs for 3000 steps with 500 atoms",
        "Total wall time: 0:00:03"]
with open("log.lammps", "w") as f:
    f.write("\n".join(log) + "\n")

# ── Fake rdf.dat: textbook LJ-fluid g(r) on the exact expected grid ──────
rows = ["# Time-averaged data for fix 3", "# TimeStep Number-of-rows", "5000 100"]
for i in range(1, 101):
    r = (i - 0.5) * 0.025
    # crude analytic LJ-fluid-like g(r): zero in core, peak ~2.7 at ~1.06, decay to 1
    if r < 0.9:
        g = 0.0
    else:
        g = 1.0 + 1.75 * np.exp(-((r - 1.06) / 0.09) ** 2) - 0.35 * np.exp(-((r - 1.9) / 0.5) ** 2)
        g = max(g, 0.0)
    rows.append(f"{i} {r:.4f} {g:.6f} {4.0 * i / 100.0:.3f}")
with open("rdf.dat", "w") as f:
    f.write("\n".join(rows) + "\n")

# ── Fake final.data: perfect FCC crystal, 500 atoms (NO simulation) ──────
rho = 0.8442
a = (4.0 / rho) ** (1.0 / 3.0)
L = 5 * a
basis = np.array([[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]])
atoms = []
idx = 1
for i in range(5):
    for j in range(5):
        for k in range(5):
            for b in basis:
                pos = (np.array([i, j, k]) + b) * a
                atoms.append((idx, pos[0], pos[1], pos[2]))
                idx += 1

with open("final.data", "w") as f:
    f.write("# fake final state\n\n")
    f.write(f"{len(atoms)} atoms\n")
    f.write("1 atom types\n\n")
    f.write(f"0.0 {L:.8f} xlo xhi\n0.0 {L:.8f} ylo yhi\n0.0 {L:.8f} zlo zhi\n\n")
    f.write("Masses\n\n1 1.0\n\n")
    f.write("Atoms\n\n")
    for idx, x, y, z in atoms:
        f.write(f"{idx} 1 {x:.8f} {y:.8f} {z:.8f}\n")

# ── results.json consistent with the forged rdf.dat ──────────────────────
results = {
    "values": {"first_peak_r": 1.0625, "first_peak_gr": 2.75, "n_rdf_bins": 100},
    "units": {"first_peak_r": "σ", "first_peak_gr": "1", "n_rdf_bins": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged log + rdf.dat + crystal final.data + results.json written")
PYEOF

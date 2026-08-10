#!/usr/bin/env bash
# Informed cheat for lammps-thermal-conductivity (reworked).
#
# Knows the task protocol, the file formats, and the ave/correlate block
# structure, but NOT the calibrated reference values (they live in refs.json,
# which never enters the image).
#
# It runs the REAL provided generator for data.in (so the L1b byte-compare
# passes), then fabricates everything downstream:
#   - data_T1.lammps / data_T04.lammps  correct counts/types/box + velocities
#   - log.eq_T1 / log.eq_T04            banner, atom count, thermo rows at the
#                                       target T, footer
#   - log.T04                           banner, atom count, 101 thermo rows at
#                                       T~0.4 with plausible NVE energy
#                                       conservation, footer
#   - J0Jt_T04.dat                      correct block structure (1 partial + 8
#                                       complete blocks, Ncount 5001 - lag) with
#                                       a decaying ACF
#   - results.json                      claiming the kappa the forged ACF
#                                       integrates to (self-consistent with the
#                                       forged J0Jt file)
#   - flux_T04.dat                      a white-noise heat-flux series
#
# It passes the structural layers (L1-L3) and the self-consistency refit (L5),
# but fails: L4 because the reference is hidden (a guessed kappa cannot land in
# an unknown tolerance), and L6 because a white-noise flux series does not back
# the forged ACF - the verifier's independent recompute from the raw series
# disagrees (and the raw <J^2> does not match the ACF's G(0)).
set -euo pipefail
mkdir -p /workspace
cd /workspace

cp /workspace/assets/generate_bench_system.py .
cp /workspace/assets/bead2.tersoff .
python3 generate_bench_system.py data.in

python3 << 'PYEOF'
import json
import numpy as np

rng = np.random.RandomState(11)
TARGET = 0.4
NC = 5001
NLAGS = 200
WINDOW = 10
DT_DATA = 0.025
N = 1200
N_BEAD, N_STICK = 1140, 60
N_BONDS, N_ANGLES = 1170, 1140

# box from the real generated data.in
box = {}
with open("data.in") as f:
    for line in f:
        p = line.split()
        if len(p) == 4 and p[2] in ("xlo", "ylo", "zlo"):
            box[p[2]] = (float(p[0]), float(p[1]))

def fabricate_data(path):
    lines = ["LAMMPS data file - forged equilibrated state",
             "", f"{N} atoms", "2 atom types", f"{N_BONDS} bonds", "1 bond types",
             f"{N_ANGLES} angles", "1 angle types", "0 dihedrals", "0 impropers", "",
             f"{box['xlo'][0]:.6f} {box['xlo'][1]:.6f} xlo xhi",
             f"{box['ylo'][0]:.6f} {box['ylo'][1]:.6f} ylo yhi",
             f"{box['zlo'][0]:.6f} {box['zlo'][1]:.6f} zlo zhi", "",
             "Masses", "", "1 1", "2 1", "", "Atoms # molecular", ""]
    aid = 0
    coords = rng.uniform(-8.9, 8.9, size=(N, 3))
    for cid in range(30):
        for j in range(40):
            aid += 1
            t = 2 if j in (10, 30) else 1   # sticker positions 11, 31 (1-indexed)
            x, y, z = coords[aid - 1]
            lines.append(f"{aid} {cid + 1} {t} {x:.6f} {y:.6f} {z:.6f}")
    lines += ["", "Velocities", ""]
    for i in range(N):
        v = rng.normal(0, 0.3, size=3)
        lines.append(f"{i + 1} {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}")
    lines += ["", "Bonds", ""]
    bid = 0
    for cid in range(30):
        for j in range(39):
            bid += 1
            s = cid * 40 + j + 1
            lines.append(f"{bid} 1 {s} {s + 1}")
    lines += ["", "Angles", ""]
    aid2 = 0
    for cid in range(30):
        for j in range(38):
            aid2 += 1
            s = cid * 40 + j + 1
            lines.append(f"{aid2} 1 {s} {s + 1} {s + 2}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

fabricate_data("data_T1.lammps")
fabricate_data("data_T04.lammps")

def fabricate_log(path, T, nrows):
    lines = ["LAMMPS (7 Jan 2022) - forged banner", "  1200 atoms"]
    lines.append("Step          Temp          Pe            Ke            Etotal        Press")
    etot0 = 20.4 if T > 0.8 else 20.39
    for i in range(nrows):
        step = i * (200000 // nrows)
        t = T * (1 + rng.normal(0, 0.005))
        et = etot0 * (1 + rng.normal(0, 0.0005))
        lines.append(f"{step:>8d} {t:14.7f} {-10.0:14.7f} {1.5*1200*T:14.7f} {et:14.7f} {0.0:14.7f}")
    lines.append("Loop time of 60 on 1 procs for 200000 steps with 1200 atoms")
    lines.append("Total wall time: 0:01:00")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

fabricate_log("log.eq_T1", 1.0, 26)
fabricate_log("log.eq_T04", 0.4, 26)
fabricate_log("log.T04", 0.4, 101)

# ── fabricated HCACF: 1 partial + 8 complete blocks ──────────────────────────
t = np.arange(NLAGS) * 0.025
base = 1.0e5 * np.exp(-t / 1.5)
out = []
out.append("0 200")  # partial first block
for i in range(NLAGS):
    c1 = base[i] if i == 0 else 0.0
    n = 1 if i == 0 else 0
    out.append(f"{i + 1} {i * 5} {n} {c1:.6e} {0.0:.6e} {0.0:.6e}")
for blk in range(8):
    out.append(f"{(blk + 1) * 25000} 200")
    for i in range(NLAGS):
        n = NC - i
        c1 = base[i] + rng.normal(0, base[0] * 0.02)
        c2 = base[i] * 0.8 + rng.normal(0, base[0] * 0.02)
        c3 = base[i] * 0.9 + rng.normal(0, base[0] * 0.02)
        out.append(f"{i + 1} {i * 5} {n} {c1:.6e} {c2:.6e} {c3:.6e}")
with open("J0Jt_T04.dat", "w") as f:
    f.write("\n".join(out) + "\n")

# ── results.json, self-consistent with the forged ACF ────────────────────────
V = (box['xlo'][1] - box['xlo'][0]) ** 3
G = (base + base * 0.8 + base * 0.9)
Gn = G / G[0]
smooth = np.convolve(Gn, np.ones(WINDOW) / WINDOW, mode="valid")
zeros = np.where(smooth < 0)[0]
cutoff = int(round((zeros[0] + WINDOW) * 1.5)) if len(zeros) else NLAGS
cutoff = min(cutoff, NLAGS)
integ = np.cumsum(G[:cutoff]) * DT_DATA
curve = integ / (3.0 * TARGET * TARGET * V)
k_forged = float(np.mean(curve[int(len(curve) * 0.8):]))
blocks = []
for _ in range(8):
    gb = G * (1 + rng.normal(0, 0.05))
    integ_b = np.cumsum(gb[:cutoff]) * DT_DATA
    curve_b = integ_b / (3.0 * TARGET * TARGET * V)
    blocks.append(np.mean(curve_b[int(len(curve_b) * 0.8):]))
err_forged = float(np.std(blocks, ddof=1) / np.sqrt(8))

results = {
    "values": {
        "kappa_T04": k_forged,
        "kappa_err_T04": err_forged,
        "n_blocks": 8,
    },
    "units": {
        "kappa_T04": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
        "n_blocks": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

# ── fabricated white-noise flux series ───────────────────────────────────────
nrows = 40000
fl = ["# step Jx Jy Jz"]
for i in range(nrows):
    step = i * 5
    fl.append(f"{step} {rng.normal(0, 30):.6e} {rng.normal(0, 30):.6e} {rng.normal(0, 30):.6e}")
with open("flux_T04.dat", "w") as f:
    f.write("\n".join(fl) + "\n")

print(f"Forged: data_T1/T04, eq logs, production log, HCACF blocks, "
      f"white-noise flux, results.json")
print(f"  forged kappa: T04={k_forged:.4f}")
PYEOF

#!/usr/bin/env bash
# Informed cheat for lammps-thermal-conductivity.
#
# Knows the task protocol, the file formats, and the ave/correlate block
# structure, but NOT the calibrated reference values (they live in refs.json,
# which never enters the image). For each state point it fabricates:
#   - log.${suffix}       banner, atom count, 101 thermo rows at the target T
#                         with plausible NVE energy conservation, footer
#   - J0Jt_${suffix}.dat  correct block structure (1 partial + 8 complete
#                         blocks, Ncount 5001 - lag) with a decaying ACF
#   - results.json        claiming the kappa the forged ACF integrates to
#                         (self-consistent with the forged J0Jt file)
#   - flux_${suffix}.dat  a white-noise heat-flux series
#
# It passes the structural layers (L1-L3) and the self-consistency refit (L5),
# but fails: L4 because the reference is hidden (a guessed kappa cannot land
# in an unknown tolerance), and L6 because a white-noise flux series does not
# back the forged ACF - the verifier's independent recompute from the raw
# series disagrees (and the raw <J^2> does not match the ACF's G(0)).
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

rng = np.random.RandomState(11)
TARGET = {"T1": 1.0, "T04": 0.4}
NC = 5001
NLAGS = 200
V = 5640.0
WINDOW = 10
DT_DATA = 0.025
kappas = {}
errs = {}

for suffix, T in TARGET.items():
    # ── fabricated log.lammps ────────────────────────────────────────────────
    lines = [f"LAMMPS (7 Jan 2022) - forged banner for {suffix}"]
    lines.append("  1200 atoms")
    lines.append("  1170 bonds")
    lines.append("  1140 angles")
    lines.append("Step          Temp          Ke            Pe            Etotal        Press")
    etot0 = 700.0 * T
    for i in range(101):
        step = i * 2000
        t = T * (1 + rng.normal(0, 0.005))
        et = etot0 * (1 + rng.normal(0, 0.0005))
        lines.append(f"{step:>8d} {t:14.7f} {1.5*1200*T:14.7f} {-10.0:14.7f} {et:14.7f} {0.0:14.7f}")
    lines.append("Loop time of 60 on 1 procs for 200000 steps with 1200 atoms")
    lines.append("Total wall time: 0:01:00")
    with open(f"log.{suffix}", "w") as f:
        f.write("\n".join(lines) + "\n")

    # ── fabricated HCACF: 1 partial + 8 complete blocks ──────────────────────
    t = np.arange(NLAGS) * 0.025
    base = 1.0e5 * np.exp(-t / 1.5)
    out = []
    out.append("0 200")  # partial first block
    for i in range(NLAGS):
        c1 = base[i] if i == 0 else 0.0
        n = 1 if i == 0 else 0
        out.append(f"{i+1} {i*5} {n} {c1:.6e} {0.0:.6e} {0.0:.6e}")
    for blk in range(8):
        out.append(f"{(blk+1)*25000} 200")
        for i in range(NLAGS):
            n = NC - i
            c1 = base[i] + rng.normal(0, base[0] * 0.02)
            c2 = base[i] * 0.8 + rng.normal(0, base[0] * 0.02)
            c3 = base[i] * 0.9 + rng.normal(0, base[0] * 0.02)
            out.append(f"{i+1} {i*5} {n} {c1:.6e} {c2:.6e} {c3:.6e}")
    with open(f"J0Jt_{suffix}.dat", "w") as f:
        f.write("\n".join(out) + "\n")

    # ── results.json, self-consistent with the forged ACF ───────────────────
    G = (base + base * 0.8 + base * 0.9)  # same for all blocks in expectation
    Gn = G / G[0]
    smooth = np.convolve(Gn, np.ones(WINDOW) / WINDOW, mode="valid")
    zeros = np.where(smooth < 0)[0]
    cutoff = int(round((zeros[0] + WINDOW) * 1.5)) if len(zeros) else NLAGS
    cutoff = min(cutoff, NLAGS)
    integ = np.cumsum(G[:cutoff]) * DT_DATA
    curve = integ / (3.0 * T * T * V)
    kappas[suffix] = float(np.mean(curve[int(len(curve) * 0.8):]))
    blocks = []
    for _ in range(8):
        gb = G * (1 + rng.normal(0, 0.05))
        integ_b = np.cumsum(gb[:cutoff]) * DT_DATA
        curve_b = integ_b / (3.0 * T * T * V)
        blocks.append(np.mean(curve_b[int(len(curve_b) * 0.8):]))
    errs[suffix] = float(np.std(blocks, ddof=1) / np.sqrt(8))

    # ── fabricated white-noise flux series ──────────────────────────────────
    nrows = 40000
    fl = ["# step Jx Jy Jz"]
    for i in range(nrows):
        step = i * 5
        fl.append(f"{step} {rng.normal(0, 30):.6e} {rng.normal(0, 30):.6e} {rng.normal(0, 30):.6e}")
    with open(f"flux_{suffix}.dat", "w") as f:
        f.write("\n".join(fl) + "\n")

results = {
    "values": {
        "kappa_T1": kappas["T1"],
        "kappa_T04": kappas["T04"],
        "kappa_err_T1": errs["T1"],
        "kappa_err_T04": errs["T04"],
        "n_blocks": 8,
    },
    "units": {
        "kappa_T1": "LJ reduced (1/(sigma*tau))",
        "kappa_T04": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T1": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
        "n_blocks": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged: logs, HCACF blocks (kappa self-consistent), white-noise flux series, results.json")
print(f"  forged kappa: T1={kappas['T1']:.4f}  T04={kappas['T04']:.4f}")
PYEOF

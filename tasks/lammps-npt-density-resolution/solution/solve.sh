#!/usr/bin/env bash
# Oracle solution for lammps-npt-density-resolution.
#
# Two NPT productions differing only in the applied pressure. The means
# differ by far more than the compressibility of the liquid can account for
# — that difference is two trajectories decorrelating, not a pressure
# effect — and the block-averaged standard error shows why the run cannot
# resolve the real effect at all.
set -euo pipefail
cd /workspace

sed -e 's/__PRESSURE__/1.0/g'      -e 's/__OUTDATA__/after_npt_earth.data/' \
    assets/npt_template.in > npt_earth.in
sed -e 's/__PRESSURE__/0.005922/g' -e 's/__OUTDATA__/after_npt_mars.data/' \
    assets/npt_template.in > npt_mars.in

export OMP_NUM_THREADS=1
lmp_serial -in npt_earth.in -log log_earth.lammps
lmp_serial -in npt_mars.in  -log log_mars.lammps

python3 << 'PYEOF'
import json
import re

import numpy as np

WINDOW_FROM = 10000     # analysis window is step > WINDOW_FROM
N_BLOCKS = 4
K_B = 1.380649e-23      # J/K
T = 298.0               # K
ATM_PA = 101325.0
P_MARS_ATM = 0.005922


def window(log_path):
    """Analysis-window rows: step temp press vol pe etotal density."""
    with open(log_path) as f:
        log = f.read()
    segments, cur = [], None
    for line in log.splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s, re.IGNORECASE):
            cur = []
            segments.append(cur)
            continue
        if cur is not None and re.match(r"^\d+\s+[-\d.eE+]", s):
            cur.append([float(x) for x in s.split()])
        if "Loop time" in line:
            cur = None
    if not segments:
        raise SystemExit(f"no thermo table in {log_path}")
    rows = np.array(segments[-1])
    return rows[rows[:, 0] > WINDOW_FROM]


def block_sem(x):
    """Standard error from N_BLOCKS contiguous blocks of equal length."""
    size = len(x) // N_BLOCKS
    means = np.array([x[i * size:(i + 1) * size].mean() for i in range(N_BLOCKS)])
    return means.std(ddof=1) / np.sqrt(N_BLOCKS)


earth, mars = window("log_earth.lammps"), window("log_mars.lammps")
assert len(earth) == len(mars), "the two windows differ in length"

rho_e, rho_m = earth[:, 6].mean(), mars[:, 6].mean()
sem_e, sem_m = block_sem(earth[:, 6]), block_sem(mars[:, 6])
combined_sem = float(np.sqrt(sem_e ** 2 + sem_m ** 2))

# Isothermal compressibility from the Earth run's volume fluctuations.
V = earth[:, 3] * 1e-30                      # A^3 -> m^3
kappa_T = float(((V - V.mean()) ** 2).mean() / (V.mean() * K_B * T))

delta_P = (1.0 - P_MARS_ATM) * ATM_PA
predicted = float(rho_e * kappa_T * delta_P)
resolvable = int(predicted > combined_sem)

results = {
    "values": {
        "density_earth": float(rho_e),
        "density_mars": float(rho_m),
        "density_difference": float(rho_e - rho_m),
        "block_sem_earth": float(sem_e),
        "block_sem_mars": float(sem_m),
        "combined_sem": combined_sem,
        "kappa_T": kappa_T,
        "predicted_delta_rho": predicted,
        "n_window_rows": int(len(earth)),
        "resolvable": resolvable,
    },
    "units": {
        "density_earth": "g/cm^3",
        "density_mars": "g/cm^3",
        "density_difference": "g/cm^3",
        "block_sem_earth": "g/cm^3",
        "block_sem_mars": "g/cm^3",
        "combined_sem": "g/cm^3",
        "kappa_T": "1/Pa",
        "predicted_delta_rho": "g/cm^3",
        "n_window_rows": "1",
        "resolvable": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Earth {rho_e:.5f} +/- {sem_e:.5f}   Mars {rho_m:.5f} +/- {sem_m:.5f} g/cm^3")
print(f"observed difference   = {rho_e - rho_m:+.6f} g/cm^3")
print(f"kappa_T               = {kappa_T:.3e} /Pa ({kappa_T * 1e9:.2f} GPa^-1)")
print(f"predicted d(rho)      = {predicted:.6f} g/cm^3")
print(f"combined block SEM    = {combined_sem:.6f} g/cm^3")
print(f"-> predicted effect is {combined_sem / predicted:.0f}x below the noise "
      f"floor; resolvable={resolvable}")
PYEOF

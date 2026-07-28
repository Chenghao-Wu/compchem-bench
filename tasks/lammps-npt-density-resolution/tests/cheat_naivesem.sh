#!/usr/bin/env bash
# Informed near-miss: the statistically naive agent.
#
# Everything here is real. Both conditions are actually simulated, both logs
# and both final configurations are genuine, the densities are correctly
# averaged over the right window, kappa_T is correctly derived from the
# volume fluctuations, and the verdict it reaches (resolvable=0) is the
# right one.
#
# Its single error is the one this task exists to catch: it estimates the
# uncertainty as sigma/sqrt(N) over the 100 thermo rows, as if consecutive
# NPT samples were independent draws. They are not — the barostat correlates
# them over roughly a picosecond — so the naive error bar comes out several
# times too small.
#
# Passes layers 1-4 (real inputs, real logs) and would pass 8 and 9 on
# merit. Must FAIL at layer 5: the verifier re-derives the block-averaged
# standard error from the agent's own logs, and sigma/sqrt(N) does not
# match it. Getting the right answer with the wrong error bar is not a
# resolution analysis.
set -euo pipefail
cd /workspace

sed -e 's/__PRESSURE__/1.0/g'      -e 's/__OUTDATA__/after_npt_earth.data/' \
    assets/npt_template.in > npt_earth.in
sed -e 's/__PRESSURE__/0.005922/g' -e 's/__OUTDATA__/after_npt_mars.data/' \
    assets/npt_template.in > npt_mars.in

export OMP_NUM_THREADS=1
lmp_serial -in npt_earth.in -log log_earth.lammps > /dev/null 2>&1
lmp_serial -in npt_mars.in  -log log_mars.lammps  > /dev/null 2>&1

python3 << 'PYEOF'
import json
import re

import numpy as np

WINDOW_FROM = 10000
K_B = 1.380649e-23
T = 298.0
ATM_PA = 101325.0


def window(path):
    segs, cur = [], None
    for line in open(path).read().splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s, re.IGNORECASE):
            cur = []
            segs.append(cur)
            continue
        if cur is not None and re.match(r"^\d+\s+[-\d.eE+]", s):
            cur.append([float(x) for x in s.split()])
        if "Loop time" in line:
            cur = None
    rows = np.array(segs[-1])
    return rows[rows[:, 0] > WINDOW_FROM]


e, m = window("log_earth.lammps"), window("log_mars.lammps")
rho_e, rho_m = e[:, 6].mean(), m[:, 6].mean()

# The error: treat correlated samples as independent.
sem_e = float(e[:, 6].std(ddof=1) / np.sqrt(len(e)))
sem_m = float(m[:, 6].std(ddof=1) / np.sqrt(len(m)))
combined = float(np.sqrt(sem_e ** 2 + sem_m ** 2))

V = e[:, 3] * 1e-30
kappa = float(((V - V.mean()) ** 2).mean() / (V.mean() * K_B * T))
pred = float(rho_e * kappa * (1.0 - 0.005922) * ATM_PA)

values = {
    "density_earth": float(rho_e),
    "density_mars": float(rho_m),
    "density_difference": float(rho_e - rho_m),
    "block_sem_earth": sem_e,
    "block_sem_mars": sem_m,
    "combined_sem": combined,
    "kappa_T": kappa,
    "predicted_delta_rho": pred,
    "n_window_rows": int(len(e)),
    "resolvable": int(pred > combined),
}
units = {k: "g/cm^3" for k in values}
units["kappa_T"] = "1/Pa"
units["n_window_rows"] = "1"
units["resolvable"] = "1"
with open("results.json", "w") as f:
    json.dump({"values": values, "units": units}, f, indent=2)
print(f"Everything real; uncertainty from sigma/sqrt(N): "
      f"combined SEM={combined:.6f} g/cm^3 (block averaging gives several "
      f"times more)")
PYEOF

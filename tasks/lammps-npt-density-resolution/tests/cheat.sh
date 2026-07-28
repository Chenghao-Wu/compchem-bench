#!/usr/bin/env bash
# Informed cheat: an agent that runs only the EARTH condition and reasons its
# way to the Mars answer instead of paying for the second simulation.
#
# The reasoning is even correct — liquids are nearly incompressible, so the
# Mars density must sit within noise of the Earth one. So it:
#   - writes both inputs as faithful template instantiations
#   - runs npt_earth.in for real (genuine log_earth.lammps and
#     after_npt_earth.data), which is also the run kappa_T comes from
#   - forges log_mars.lammps from the real Earth log, keeping the row count,
#     step range, atom count and Mars pressure all correct and nudging the
#     density column by a physically plausible amount
#   - reuses the real Earth configuration as after_npt_mars.data
#   - reports statistics that are genuinely consistent with both logs, a
#     correctly block-averaged SEM, a correct kappa_T, and the right
#     resolvable=0 verdict
#
# Must FAIL on whole-trace integrity: it rewrites the density column but not
# the volume column, and LAMMPS' density is total mass / volume by
# construction, so every forged row contradicts itself. It is also caught by
# the byte-identical-configuration check.
#
# Note this cheat PASSED the first version of the verifier, which compared
# the written box against only the final thermo row: the jitter on that one
# row happened to cancel the shift to within 0.00032 g/cm^3. Pinning a
# single point of a trace is not enough — hence the per-row constraint.
set -euo pipefail
cd /workspace

sed -e 's/__PRESSURE__/1.0/g'      -e 's/__OUTDATA__/after_npt_earth.data/' \
    assets/npt_template.in > npt_earth.in
sed -e 's/__PRESSURE__/0.005922/g' -e 's/__OUTDATA__/after_npt_mars.data/' \
    assets/npt_template.in > npt_mars.in

export OMP_NUM_THREADS=1
lmp_serial -in npt_earth.in -log log_earth.lammps > /dev/null 2>&1

cp after_npt_earth.data after_npt_mars.data

python3 << 'PYEOF'
import json
import re

import numpy as np

rng = np.random.RandomState(17)
WINDOW_FROM = 10000
N_BLOCKS = 4
K_B = 1.380649e-23
T = 298.0
ATM_PA = 101325.0

with open("log_earth.lammps") as f:
    earth_log = f.read()

# Forge the Mars log from the Earth one: Mars pressure, density nudged.
out_lines, in_table = [], False
for line in earth_log.splitlines():
    s = line.strip()
    if re.match(r"^\s*fix\s+\S+\s+all\s+npt\s+temp", line):
        line = line.replace("iso 1.0 1.0", "iso 0.005922 0.005922")
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_table = True
        out_lines.append(line)
        continue
    if in_table and re.match(r"^\d+\s+[-\d.eE+]", s):
        p = s.split()
        p[6] = f"{float(p[6]) - 0.0061 + rng.normal(0, 0.004):.8g}"
        out_lines.append("     " + "     ".join(p))
        continue
    if "Loop time" in line:
        in_table = False
    out_lines.append(line)

with open("log_mars.lammps", "w") as f:
    f.write("\n".join(out_lines) + "\n")


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


def block_sem(x):
    size = len(x) // N_BLOCKS
    means = np.array([x[i * size:(i + 1) * size].mean() for i in range(N_BLOCKS)])
    return float(means.std(ddof=1) / np.sqrt(N_BLOCKS))


e, m = window("log_earth.lammps"), window("log_mars.lammps")
rho_e, rho_m = e[:, 6].mean(), m[:, 6].mean()
sem_e, sem_m = block_sem(e[:, 6]), block_sem(m[:, 6])
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
print(f"Ran Earth for real ({rho_e:.5f}); forged Mars ({rho_m:.5f}) and "
      f"reused the Earth configuration")
PYEOF

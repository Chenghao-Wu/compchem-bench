#!/usr/bin/env bash
# Cheat 2 — half-fix: knows the Einstein factor is 6 in 3D, but reuses the
# colleague's fit window (100-500 ps, the constants left in analyze_msd.py)
# instead of the requested 50-100 ps. Reports D = 5.708e-5 cm^2/s with fully
# correct audit verdicts.
# Must FAIL at the second decoy guard: right factor, wrong window.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

import numpy as np

data = np.loadtxt("assets/msd.dat")
step, mx, my, mz, mt = data.T
t = step * 0.002

sel = (t >= 100.0) & (t <= 500.0)
slope, intercept = np.polyfit(t[sel], mt[sel], 1)
resid = mt[sel] - (slope * t[sel] + intercept)
r2 = 1 - np.sum(resid**2) / np.sum((mt[sel] - mt[sel].mean())**2)

results = {
    "values": {
        "D_cm2_s": slope / 6.0 * 1e-4,
        "slope_A2_per_ps": slope,
        "intercept_A2": intercept,
        "r_squared": r2,
        "n_fit_points": int(sel.sum()),
        "D_x_cm2_s": np.polyfit(t[sel], mx[sel], 1)[0] / 2 * 1e-4,
        "D_y_cm2_s": np.polyfit(t[sel], my[sel], 1)[0] / 2 * 1e-4,
        "D_z_cm2_s": np.polyfit(t[sel], mz[sel], 1)[0] / 2 * 1e-4,
    },
    "units": {
        "D_cm2_s": "cm^2/s",
        "slope_A2_per_ps": "A^2/ps",
        "intercept_A2": "A^2",
        "r_squared": "1",
        "n_fit_points": "1",
        "D_x_cm2_s": "cm^2/s",
        "D_y_cm2_s": "cm^2/s",
        "D_z_cm2_s": "cm^2/s",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

audit = {
    "colleague_D_correct": False,
    "colleague_window_correct": False,
    "colleague_plausibility_claim_correct": False,
    "identified_errors": ["wrong_einstein_factor", "window_mismatch"],
}
with open("audit.json", "w") as f:
    json.dump(audit, f, indent=2)

with open("audit.md", "w") as f:
    f.write("The colleague used slope/2 instead of slope/6 and the wrong window. " * 40)
print(f"Half-fix cheat: D(100-500 ps, slope/6) = {slope/6*1e-4:.4e} cm^2/s")
PYEOF

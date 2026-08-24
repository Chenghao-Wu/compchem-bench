#!/usr/bin/env bash
# Oracle solution for lammps-msd-diffusion-audit.
#
# Audit findings:
#   1. wrong_einstein_factor — analyze_msd.py computes D = slope/2 from the
#      TOTAL 3D MSD. In 3D, <|r(t)-r(0)|^2> = 6 D t (2 D t is the PER-AXIS
#      relation). The headline D is therefore 3x too large — which the
#      colleague's own per-axis values expose: mean(D_x,D_y,D_z) = 5.71e-5
#      cm^2/s, exactly 1/3 of the claimed 1.71e-4 cm^2/s.
#   2. window_mismatch — the summary/README claim a 50-100 ps fit window,
#      but analyze_msd.py sets FIT_LO, FIT_HI = 100, 500 and its slope
#      (3.4248 A^2/ps) is the 100-500 ps slope; a genuine 50-100 ps fit
#      gives 3.6765 A^2/ps.
#   The plausibility claim also fails: 1.71e-4 cm^2/s is ~7x the
#   experimental self-diffusivity of water at 300 K (2.3e-5 cm^2/s) and
#   ~3x the known TIP3P value (~5-6e-5 cm^2/s, TIP3P overestimates).
#
# Correct analysis (50-100 ps closed interval, fit with intercept,
# D = slope/6): D = 6.13e-5 cm^2/s.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import re

import numpy as np

# ---- time axis from the actual input deck (units real -> fs) ----
with open("assets/in.lammps") as f:
    inp = f.read()
m = re.search(r"^\s*timestep\s+([\d.eE+]+)", inp, re.MULTILINE)
assert m, "no timestep command in in.lammps"
dt_ps = float(m.group(1)) / 1000.0  # fs -> ps
assert "units           real" in inp

data = np.loadtxt("assets/msd.dat")
step, mx, my, mz, mt = data.T
t = step * dt_ps

LO, HI = 50.0, 100.0
sel = (t >= LO) & (t <= HI)
assert sel.sum() == 101, f"expected 101 samples in [{LO}, {HI}] ps, got {sel.sum()}"

def einstein_fit(tt, yy, dim_factor):
    slope, intercept = np.polyfit(tt, yy, 1)
    resid = yy - (slope * tt + intercept)
    r2 = 1 - np.sum(resid**2) / np.sum((yy - yy.mean())**2)
    return slope, intercept, r2, slope / dim_factor

slope, intercept, r2, D_A2ps = einstein_fit(t[sel], mt[sel], 6.0)   # 3D total MSD
Dx = einstein_fit(t[sel], mx[sel], 2.0)[3]                        # per axis: 2D
Dy = einstein_fit(t[sel], my[sel], 2.0)[3]
Dz = einstein_fit(t[sel], mz[sel], 2.0)[3]

A2PS_TO_CM2S = 1e-4  # 1 A^2/ps = 1e-4 cm^2/s

results = {
    "values": {
        "D_cm2_s": D_A2ps * A2PS_TO_CM2S,
        "slope_A2_per_ps": slope,
        "intercept_A2": intercept,
        "r_squared": r2,
        "n_fit_points": int(sel.sum()),
        "D_x_cm2_s": Dx * A2PS_TO_CM2S,
        "D_y_cm2_s": Dy * A2PS_TO_CM2S,
        "D_z_cm2_s": Dz * A2PS_TO_CM2S,
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

# evidence numbers for the narrative
sel_c = (t >= 100.0) & (t <= 500.0)
slope_c = np.polyfit(t[sel_c], mt[sel_c], 1)[0]
beta = np.polyfit(np.log(t[sel]), np.log(mt[sel]), 1)[0]

with open("audit.md", "w") as f:
    f.write(f"""# Audit: self-diffusion coefficient of TIP3P water (50-100 ps window)

## Verdict

The colleague's headline value D = 1.712e-4 cm^2/s is **wrong**, the claimed
50-100 ps fit window was **not** the window actually fitted, and the claim
that the value agrees with the established diffusivity of water is **false**.

## Error 1: wrong Einstein factor (definition)

`analyze_msd.py` fits the *total* (3D) MSD and then computes `D = slope / 2`
with the comment "MSD = 2 D t". The 3D Einstein relation for the total MSD is

    <|r(t) - r(0)|^2> = 6 D t        (per axis: <(x-x0)^2> = 2 D t)

so the total-MSD slope must be divided by 6, not 2. The colleague's own
per-axis values expose the inconsistency: the components in
`diffusion_summary.txt` (6.71, 5.15, 5.26 x 1e-5 cm^2/s) average to
5.71e-5 cm^2/s — exactly one third of the headline 1.71e-4 cm^2/s. A correct
headline D must equal the mean of the per-axis coefficients.

## Error 2: fit-window mismatch

The summary and README claim the fit used the requested 50-100 ps window,
but `analyze_msd.py` sets `FIT_LO, FIT_HI = 100.0, 500.0`, and the reported
slope 3.4248 A^2/ps is the 100-500 ps slope. A genuine fit over 50-100 ps
(closed interval, 101 samples at 0.5 ps spacing) gives slope =
{slope:.4f} A^2/ps, not 3.4248 A^2/ps. The plot `msd_analysis.png` also shows
the fit line over 100-500 ps.

## Plausibility

1.712e-4 cm^2/s is ~7x the experimental self-diffusion coefficient of water
at 300 K (2.3e-5 cm^2/s) and ~3x the known TIP3P model value
(~5-6e-5 cm^2/s; TIP3P is known to overestimate experiment). The claim of
"good agreement with the well-established diffusivity of liquid water" does
not survive any comparison.

## Corrected analysis

- time axis: step x {dt_ps*1000:.1f} fs (from `timestep` in `in.lammps`,
  real units), MSD written every 250 steps -> 0.5 ps spacing
- fit: total MSD vs t, least squares WITH intercept, closed interval
  50 <= t <= 100 ps (101 points)
- slope = {slope:.4f} A^2/ps, intercept = {intercept:.2f} A^2, R^2 = {r2:.5f}
- D = slope/6 = {D_A2ps:.4f} A^2/ps = {D_A2ps*1e-4:.3e} cm^2/s

## Validation

- Regime: R^2 = {r2:.5f} and the log-log slope of MSD vs t in the window is
  {beta:.3f} (approximately 1 -> diffusive, not ballistic).
- Isotropy: D_x, D_y, D_z = {Dx*1e-4:.2e}, {Dy*1e-4:.2e}, {Dz*1e-4:.2e} cm^2/s
  — mutually consistent within single-trajectory noise, and their mean
  reproduces the headline D, as it must.
- Physics: the corrected value 6.13e-5 cm^2/s sits in the established TIP3P
  range at 300 K (~5-6e-5 cm^2/s), above the experimental 2.3e-5 cm^2/s as
  expected for this force field.
""")
print(f"D(50-100 ps) = {D_A2ps*1e-4:.4e} cm^2/s  (slope {slope:.4f} A^2/ps, R^2 {r2:.5f}, n=101)")
PYEOF

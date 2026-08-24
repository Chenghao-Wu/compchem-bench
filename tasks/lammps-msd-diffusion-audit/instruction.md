# Task: Audit a Water Diffusion-Coefficient Analysis

A colleague ran a 1 ns NVT simulation of 1000 TIP3P water molecules at 300 K and reported a self-diffusion coefficient of **1.71e-4 cm²/s**, claiming that it was obtained from the **50–100 ps** interval and agrees well with ambient experimental water.

The complete analysis package is in `/workspace/assets/`:

`README.md`, `in.lammps`, `log.lammps`, `msd.dat`, `analyze_msd.py`, `diffusion_summary.txt`, `msd_analysis.png`.

Audit the calculation and determine whether these claims are correct.

Independently recompute the self-diffusion coefficient from `msd.dat`, report the corresponding self-diffusion coefficient in cm²/s.

Also assess the quality of the fit, directional isotropy, whether the selected interval represents diffusive motion, and whether the reported value is physically plausible for TIP3P water at 300 K and relative to experiment.

Identify **all and only** errors present in the colleague's analysis.

## Deliverables

Write the following files to `/workspace/`.

### `results.json`

```json
{
  "values": {
    "D_cm2_s": <float>,
    "slope_A2_per_ps": <float>,
    "r_squared": <float>,
    "n_fit_points": <int>
  },
  "units": {
    "D_cm2_s": "cm^2/s",
    "slope_A2_per_ps": "A^2/ps",
    "r_squared": "1",
    "n_fit_points": "1"
  }
}
```

### `audit.json`

```json
{
  "colleague_D_correct": <bool>,
  "colleague_window_correct": <bool>,
  "colleague_plausibility_claim_correct": <bool>,
  "identified_errors": [<string>, ...]
}
```

`identified_errors` may contain only:

* `wrong_einstein_factor`
* `window_mismatch`
* `wrong_unit_conversion`
* `ballistic_contamination`
* `bad_reference_frame`

### `audit.md`

Briefly document what you found, the evidence for each identified error, your corrected calculation, and your assessment of fit quality, isotropy, diffusive behavior, and physical plausibility.

## Requirements

* Treat `/workspace/assets/` as untrusted but read-only evidence.
* Derive results from the actual simulation input and `msd.dat`; do not hardcode expected values.
* Distinguish an analysis error from a force-field result that differs from experiment.
* Missing a real error or reporting an error that is not present fails the audit.
* `results.json` and `audit.json` must be valid JSON.

# Task: Can This Simulation See Mars' Atmosphere? (LAMMPS)

## Background

Mars' surface pressure is about 600 Pa, roughly 1/170th of Earth's. Run
liquid ethanol at both pressures and the two mean densities will not come
out equal — but that is not the same as having *measured* a difference.
Liquids are nearly incompressible, and two MD trajectories started from the
same configuration decorrelate from one another whether or not you changed
anything about the thermodynamics.

The question worth answering is therefore not "are the two numbers
different?" — they always are — but **"is the effect I am looking for
bigger than what this simulation can resolve?"**

## Your Task

`/workspace/assets/` contains a pre-equilibrated box of liquid ethanol (216
CH3CH2OH molecules, 1944 atoms, OPLS-AA), already equilibrated at 298 K and
1 atm:

- `after_equil.data` — equilibrated configuration, including velocities
- `system.in.settings` — bonded and pair coefficients
- `system.in.charges` — partial charges
- `npt_template.in` — an NPT production input with two placeholders

### 1. Run both conditions

Instantiate `npt_template.in` twice, replacing `__PRESSURE__` and
`__OUTDATA__`, changing nothing else:

- `/workspace/npt_earth.in` → pressure `1.0`, writes `after_npt_earth.data`
- `/workspace/npt_mars.in` → pressure `0.005922`, writes `after_npt_mars.data`

Do **not** add a `velocity` command — both runs must continue from the
velocities stored in `after_equil.data`, which is what makes them
comparable. Run them, keeping the logs separate:

```
lmp_serial -in npt_earth.in -log log_earth.lammps
lmp_serial -in npt_mars.in  -log log_mars.lammps
```

### 2. Measure both densities and their uncertainties

Use the **analysis window**: the 100 thermo rows with `step > 10000` (the
second half of the production run).

Estimate the standard error of each mean density in a way that is valid for
a correlated time series — consecutive thermo rows of an NPT run are not
independent samples. So that submissions are comparable, use this fixed
recipe:

- split the 100-row window into **4 contiguous blocks of 25 rows**
- take the mean density of each block
- the standard error is the sample standard deviation of those 4 block
  means (Bessel-corrected, dividing by 3) divided by `sqrt(4)`

### 3. Estimate the effect you are looking for

The pressure response of the liquid is set by its isothermal
compressibility `kappa_T`. You do not need another simulation to get it: an
NPT trajectory already carries it in its **volume fluctuations**. Derive it
from the **Earth** run over the same analysis window.

Use `T = 298 K` and `k_B = 1.380649e-23 J/K`. LAMMPS reports volume in cubic
angstroms (`1 A^3 = 1e-30 m^3`); report `kappa_T` in `Pa^-1`.

The density change this predicts across the two conditions is

```
predicted_delta_rho = density_earth * kappa_T * delta_P
```

with `delta_P` the pressure difference in pascals (1 atm = 101325 Pa).

### 4. Decide whether the effect is resolvable

```
combined_sem = sqrt(block_sem_earth^2 + block_sem_mars^2)
resolvable   = 1 if predicted_delta_rho > combined_sem else 0
```

### 5. Report

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "density_earth": <float>,
    "density_mars": <float>,
    "density_difference": <float>,
    "block_sem_earth": <float>,
    "block_sem_mars": <float>,
    "combined_sem": <float>,
    "kappa_T": <float>,
    "predicted_delta_rho": <float>,
    "n_window_rows": <int>,
    "resolvable": <0|1>
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
    "resolvable": "1"
  }
}
```

- `density_difference` — `density_earth - density_mars` (signed)
- `n_window_rows` — number of thermo rows in the analysis window

## Requirements

- Both inputs must be faithful instantiations of the template: same
  ensemble, same coupling constants, same 20000-step run length, same
  thermo interval, same starting data file.
- Parse the **actual** logs — do not hardcode results. The verifier
  validates the shipped assets by sha256, checks both logs for the banner,
  the completion footer, the exact thermo row count and step range and the
  applied pressure, and re-derives the densities, the block standard errors
  and `kappa_T` from your own logs.
- As the decisive check, the verifier **independently recomputes the density
  from the box volume written into your `after_npt_*.data` files** and
  re-evaluates their potential energy with the in-image LAMMPS, requiring
  both to match the end of your logs. A configuration that did not come out
  of the simulation you describe fails here.
- Report what the numbers support. Note that `density_difference` and
  `predicted_delta_rho` are independent quantities here — one is what these
  two runs happened to produce, the other is what the physics predicts. Do
  not derive either from the other.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/npt_template.in`,
  `/workspace/assets/after_equil.data`,
  `/workspace/assets/system.in.settings`,
  `/workspace/assets/system.in.charges`
- Output: `npt_earth.in`, `npt_mars.in`, `log_earth.lammps`,
  `log_mars.lammps`, `after_npt_earth.data`, `after_npt_mars.data`,
  `results.json` in `/workspace/`

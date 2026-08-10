# Task: Thermal Conductivity of a Sticker Melt by Green-Kubo (LAMMPS)

## Background

For an isotropic fluid, the Green-Kubo relation gives the thermal conductivity as
an integral over the equilibrium heat-flux autocorrelation function (HCACF):

    κ = (1 / (3·k_B·T²·V)) · ∫₀^∞ ⟨J(0)·J(t)⟩ dt

where J(t) is the microscopic heat-flux vector, V the box volume, T the
temperature, and k_B = 1 in the LJ units used here. The 1/3 factor is the
isotropic average over the three Cartesian components. A common pitfall is a
drifting center of mass, which adds a spurious convective term to J: the total
momentum must be zeroed and kept near zero.

The system is a sticker-functionalized bead-spring melt (40-bead chains, two
sticker beads per chain, Tersoff sticker attraction u = 18 k_B T), in LJ reduced
units. You will compute κ at T* = 0.4.

## System generation

The melt is 30 chains × 40 beads = 1200 atoms, built by the provided generator
`generate_bench_system.py` (the two provided files are in `/workspace/assets/`).
It writes a LAMMPS data file of the *initial coil* (no velocities):

```bash
cp /workspace/assets/generate_bench_system.py /workspace/assets/bead2.tersoff .
python3 generate_bench_system.py data.in
```

Each chain carries **two sticker beads** (atom type 2) at chain positions 11 and
31; the other 38 beads are regular beads (atom type 1). The generator is
deterministic — every run produces the same structure. Do **not** modify
`generate_bench_system.py`.

## Two-stage equilibration (mandatory)

A low-temperature sticker melt cannot be equilibrated directly from a random
coil — sticker association at low T is slow and the melt gets kinetically
trapped. You must first equilibrate at high temperature and then **quench**:

1. **Equilibrate at T\* = 1.0** (NVT, e.g. a Langevin thermostat) starting from
   `data.in`. Use long enough runs that temperature and energy are stationary.
2. **Quench to T\* = 0.4** in a second NVT run that **starts from the T\* = 1.0
   equilibrated state**, not from the coil.
3. Write out the equilibrated state at each temperature **including velocities**
   (`write_data`), so the next stage can start from it.

## Setting up the force field (the hard part)

The provided `bead2.tersoff` file defines the sticker potential (entry `B1 B1 B1`,
sticker strength u = 18 kT). You must assemble the full interaction model in your
LAMMPS inputs. The model is:

- **Bonds**: FENE (`bond_style fene`), constants K = 30.0, R₀ = 1.5, ε = 1.0, σ = 1.0.
- **Angles**: cosine (`angle_style cosine`), constant 1.5.
- **Non-bonded**: a **hybrid overlay** of LJ and Tersoff. The regular beads
  (type 1) interact by LJ (ε = 1.0, σ = 1.0, cutoff = 1.1225). The sticker beads
  (type 2) interact by the **Tersoff** potential from `bead2.tersoff` (element
  `B1`); their LJ interactions are disabled. Stickers of the same chain (type 2)
  must not self-interact through the many-body potential — use `special_bonds fene`.

Notes that will save you hours:

- The generated `data.in` carries **Bond and Angle sections** (and after
  equilibration, `write_data` adds **Bond/Angle Coeffs sections** to the output).
  LAMMPS requires `bond_style`/`angle_style`/`pair_style` to be defined **before**
  `read_data`, but the `bond_coeff`/`angle_coeff`/`pair_coeff` values can only be
  set **after** the box exists (i.e. after `read_data`).
- LAMMPS continuation lines use `&`, not `\`.
- **Only correct the linear momentum.** Zero the total linear momentum once at the
  start of each run and hold it near zero (e.g. `fix momentum ... linear 1 1 1`).
  Do **not** also remove net angular momentum every so often: in a small
  (1200-bead) system that drains rotational kinetic energy and the NVE run cools
  instead of staying at the target temperature.

## Production run (T\* = 0.4)

From the quenched `data_T04.lammps` (with velocities), run a **200000-step NVE**
production at T\* = 0.4 with the momentum held near zero, and accumulate the
heat-flux autocorrelation:

- Compute the per-atom kinetic/potential energy and per-atom virial, then the heat
  flux vector with `compute heat/flux`.
- **HCACF via `fix ave/correlate`**: `Nevery = 5`, `Nrepeat = 200`, `Nfreq = 25000`
  on the three heat-flux components, `type auto`, `ave one`. With a 200000-step
  run this yields **8 independent blocks** of **200 correlation lags**; a block
  starts with a marker line of two integers and its first data row has
  `Ncount = 5001` at lag 0.
- Dump the **raw heat-flux vector every 5 steps** to a separate file (a
  `fix print ... file` writing the three components each step).
- `thermo` every 2000 steps to `log.T04`.

## Computing κ from the HCACF

From `J0Jt_T04.dat`:

1. **Parse the blocks.** A block begins with a marker line holding two integers,
   followed by 200 data rows with columns
   `index TimeDelta Ncount Jx·Jx Jy·Jy Jz·Jz`. `TimeDelta` is in timesteps; the
   correlation time is τ = TimeDelta × 0.005. Discard any block whose first data
   row has `Ncount < 5001` (an incomplete block); use the remaining 8.
2. **Build G(t) = ⟨J(0)·J(t)⟩** as the sum of the three diagonal autocorrelations
   (`Jx·Jx + Jy·Jy + Jz·Jz`), averaged over the retained blocks.
3. **Choose the cutoff.** Normalize G(t) by G(0), smooth with a moving average of
   width 10, find the first index where the smoothed curve falls below zero, and
   set `cutoff = round(1.5 × (zero_index + 10))`, clamped to the series length.
4. **Integrate.** κ(t) = cumsum(G[0:cutoff]) × 0.025 / (3·k_B·T²·V), where
   0.025 = Nevery × dt is the lag spacing, T = 0.4, and V is the box volume read
   from `data_T04.lammps` ((xhi−xlo)·(yhi−ylo)·(zhi−zlo)). Report κ = mean of the
   last 20% of κ(t).
5. **Statistical error.** Compute κ per retained block with the same cutoff and
   report the standard error of the mean over blocks: std(κ_block) / √n_blocks.

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "kappa_T04": <float>,
    "kappa_err_T04": <float>,
    "n_blocks": <int>
  },
  "units": {
    "kappa_T04": "LJ reduced (1/(sigma*tau))",
    "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
    "n_blocks": "1"
  }
}
```

- `kappa_T04`: thermal conductivity at T\* = 0.4
- `kappa_err_T04`: standard error of the mean (positive, < κ)
- `n_blocks`: number of retained independent blocks (8)

## Requirements

- Build the system with the provided generator; do not modify it.
- Equilibrate at T\* = 1.0, then quench to T\* = 0.4 **starting from the T\* = 1.0
  state**; write out both equilibrated states with velocities.
- Run the 200000-step NVE production at T\* = 0.4 as specified and compute κ from
  the **actual** outputs — do not hardcode values. The verifier checks the run
  structure, re-derives κ from your `J0Jt` file with the same protocol, and
  independently recomputes the HCACF from your raw `flux` series and integrates it
  again: your reported κ, the `J0Jt` file, and the `flux` series must all tell the
  same story.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Inputs: `/workspace/assets/generate_bench_system.py`, `bead2.tersoff`
  (copy to your working directory)
- Your outputs in the working directory: `data.in`, `data_T1.lammps`,
  `data_T04.lammps`, `log.eq_T1`, `log.eq_T04`, `log.T04`, `J0Jt_T04.dat`,
  `flux_T04.dat`, `results.json`

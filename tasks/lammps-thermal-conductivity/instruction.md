# Task: Thermal Conductivity of a Sticker Melt by Green-Kubo (LAMMPS)

## Background

For an isotropic fluid, the Green-Kubo relation gives the thermal
conductivity as an integral over the equilibrium heat-flux autocorrelation
function (HCACF):

    κ = (1 / (3·k_B·T²·V)) · ∫₀^∞ ⟨J(0)·J(t)⟩ dt

where J(t) is the microscopic heat-flux vector, V the box volume, T the
temperature, and k_B = 1 in the LJ units used here. The 1/3 factor accounts
for isotropic averaging over the three Cartesian components. A common
pitfall is a drifting center of mass, which adds a spurious convective
term to J: the total momentum must be zeroed and kept near zero.

The system is a sticker-functionalized bead-spring melt (40-bead chains,
two sticker beads per chain, Tersoff sticker attraction u = 18 k_B T), in
LJ reduced units. You will compute κ at two state points: T* = 1.0 and
T* = 0.4.

## Your Task

Four input files are provided in `/workspace/assets/`: `therm.in` (the
LAMMPS input), `bead2.tersoff` (the sticker potential), and two equilibrated
initial conditions `data_T1.lammps` (T* = 1.0) and `data_T04.lammps`
(T* = 0.4), each carrying the atomic velocities for its state point.

Copy all four files to your working directory and run the provided input
once per state point (do **not** modify `therm.in`):

```bash
lmp_serial -log log.T1  -var suffix T1  -in therm.in
lmp_serial -log log.T04 -var suffix T04 -in therm.in
```

(The `-log` flag sends each run's full output — banner, box, thermo, footer — to
`log.${suffix}`; without it both runs would clobber the default `log.lammps`.)

Each run performs 200000 NVE steps with the total momentum held near zero
and produces:

- `log.${suffix}` — LAMMPS log (thermo every 2000 steps)
- `J0Jt_${suffix}.dat` — the HCACF from `fix ave/correlate` (8 independent
  blocks of 200 correlation points, `ave one`)
- `flux_${suffix}.dat` — the raw heat-flux vector sampled every 5 steps

Then, for each state point, compute κ:

1. **Parse `J0Jt_${suffix}.dat`.** The file is organized in blocks. A block
   starts with a marker line holding two integers (timestep and number of
   correlation points), followed by 200 data rows with columns
   `index TimeDelta Ncount Jx·Jx Jy·Jy Jz·Jz`. `TimeDelta` is in timesteps;
   the correlation time is τ = TimeDelta × 0.005. Discard any block whose
   first data row has `Ncount < 5001` (an incomplete first block). Use the
   remaining 8 blocks.
2. **Build G(t) = ⟨J(0)·J(t)⟩** as the sum of the three diagonal
   autocorrelations (`Jx·Jx + Jy·Jy + Jz·Jz`), averaged over the retained
   blocks.
3. **Choose the integration cutoff.** Normalize G(t) by G(0), smooth with a
   moving average of width 10, and find the first index where the smoothed
   curve falls below zero. Set `cutoff = round(1.5 × (zero_index + 10))`,
   clamped to the series length.
4. **Integrate.** κ(t) = cumsum(G[0:cutoff]) × 0.025 / (3·k_B·T²·V), where
   0.025 = Nevery × dt is the lag spacing, T is the target temperature
   (1.0 or 0.4), and V is the box volume read from the data file
   ((xhi−xlo)·(yhi−ylo)·(zhi−zlo)). Report κ = mean of the last 20% of
   κ(t).
5. **Statistical error.** Compute κ per retained block with the same cutoff,
   and report the standard error of the mean over blocks:
   std(κ_block) / √n_blocks.

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "kappa_T1": <float>,
    "kappa_T04": <float>,
    "kappa_err_T1": <float>,
    "kappa_err_T04": <float>,
    "n_blocks": <int>
  },
  "units": {
    "kappa_T1": "LJ reduced (1/(sigma*tau))",
    "kappa_T04": "LJ reduced (1/(sigma*tau))",
    "kappa_err_T1": "LJ reduced (1/(sigma*tau))",
    "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
    "n_blocks": "1"
  }
}
```

- `kappa_T1` / `kappa_T04`: thermal conductivity at T* = 1.0 / 0.4
- `kappa_err_T1` / `kappa_err_T04`: standard error of the mean (positive)
- `n_blocks`: number of retained independent blocks (8)

## Requirements

- Run the provided input at both state points; do not modify it.
- Compute κ from the **actual** outputs — do not hardcode values. The
  verifier checks the run structure, re-derives κ from your `J0Jt` files
  with the same protocol, and independently recomputes the HCACF from your
  raw `flux` time series and integrates it again: your reported κ, the
  `J0Jt` files, and the `flux` series must all tell the same story.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Inputs: `/workspace/assets/therm.in`, `bead2.tersoff`,
  `data_T1.lammps`, `data_T04.lammps` (copy to your working directory)
- Outputs: `log.T1`, `log.T04`, `J0Jt_T1.dat`, `J0Jt_T04.dat`,
  `flux_T1.dat`, `flux_T04.dat`, `results.json` in your working directory

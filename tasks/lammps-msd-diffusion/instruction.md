# Task: Self-Diffusion Coefficient from MSD (LAMMPS)

## Background

The self-diffusion coefficient D of a fluid follows from the mean-squared
displacement via the Einstein relation, MSD(t) = 6·D·t in the diffusive
(linear) regime. Getting D right means running the dynamics and fitting
**the linear part** of the MSD curve — not the ballistic short-time part.

## Your Task

A LAMMPS input `msd.in` is provided in `/workspace/assets/`. Copy it to your
working directory and run it with LAMMPS (do not modify it).

The simulation (LJ fluid, 864 atoms, ρ*=0.8442, T*=1.2, timestep 0.005τ):

- Equilibrates under NVT for 2000 steps
- Runs 10000 production steps (steps 2000–12000), printing
  `step temp pe c_msd[4]` to the thermo output every 100 steps and dumping
  unwrapped coordinates to `traj.dump` every 100 steps

After the run:

1. Keep `log.lammps` and `traj.dump` in `/workspace/`.
2. From the production thermo data, extract MSD(t) with
   t = (step − 2000) × 0.005.
3. Fit the **linear regime** of MSD(t) — use the second half of the
   production run, i.e. thermo rows with step ≥ 7000 — and extract
   D = slope / 6.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "diffusion_D": <float>,
       "n_msd_rows": <int>
     },
     "units": {
       "diffusion_D": "σ²/τ",
       "n_msd_rows": "1"
     }
   }
   ```

   - `diffusion_D`: fitted self-diffusion coefficient (LJ reduced units)
   - `n_msd_rows`: number of production thermo rows (101)

## Requirements

- Run LAMMPS with the provided input (do not modify it).
- Parse the **actual** output — do not hardcode D. The verifier checks the
  log structure (both run segments with the exact thermo row counts),
  re-fits D from your log's MSD column using the same window and requires
  agreement, and — as the decisive check — **independently recomputes the
  MSD from your `traj.dump`** (unwrapped coordinates) and fits D again:
  your reported D, the log's MSD, and the trajectory must all tell the
  same story.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/msd.in` (copy to `/workspace/`)
- Output: `log.lammps`, `traj.dump`, `results.json` in `/workspace/`

# Task: Ab Initio Molecular Dynamics of a Single Water Molecule (CP2K)

## Background

Run a short Born–Oppenheimer ab initio MD (AIMD) trajectory of a single
water molecule in the NVE ensemble with CP2K, then analyze the energy
conservation and temperature from the trajectory.

## Your Task

A CP2K input file `h2o_aimd.inp` is provided in `/workspace/assets/`. It
runs **20 NVE MD steps** of one H2O molecule (PBE / DZVP-MOLOPT-SR-GTH,
10 Å non-periodic box, timestep 0.5 fs, initial temperature 300 K).
Copy it to your working directory and run CP2K. The basis-set and
pseudopotential data files (`BASIS_MOLOPT`, `GTH_POTENTIALS`) are part of
the CP2K installation at `/opt/cp2k/data/` — copy or symlink them into
your working directory (the input references them by bare filename).

After the run completes:

1. Keep in `/workspace/` the CP2K trajectory files `h2o_aimd-1.ener`
   (MD energies) and `h2o_aimd-pos-1.xyz` (positions) — both are needed
   for verification.
2. Parse `h2o_aimd-1.ener` (columns: step, time, kinetic energy,
   temperature, potential energy, conserved quantity, CPU time) and
   compute:
   - the potential energy at the final MD step
   - the mean temperature over **all** data rows in the file
   - the drift of the conserved quantity, |Cons Qty(final) − Cons Qty(first)|
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_potential": <float, Ha>,
       "mean_temperature": <float, K>,
       "cons_qty_drift": <float, Ha>,
       "n_md_steps": <int>
     },
     "units": {
       "final_potential": "Ha",
       "mean_temperature": "K",
       "cons_qty_drift": "Ha",
       "n_md_steps": "1"
     }
   }
   ```

## Requirements

- Run CP2K with the provided input (do not modify it).
- `h2o_aimd-1.ener` must contain exactly **21 data rows** (MD steps 0
  through 20) — one header line plus 21 rows.
- Do **not** hardcode any value — the verifier re-derives every reported
  quantity from your `.ener` file and additionally runs its own
  single-point calculation on the final geometry of your position
  trajectory, requiring it to agree with the potential energy at the last
  MD step.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/h2o_aimd.inp`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `h2o_aimd.out`, `h2o_aimd-1.ener`, `h2o_aimd-pos-1.xyz`,
  `results.json` in `/workspace/`

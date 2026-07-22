# Task: Continue a Simulation from a Restart File (LAMMPS)

## Background

`/workspace/assets/equil.restart` is a LAMMPS binary restart of a 3D
Lennard-Jones fluid (500 atoms, reduced units, lj/cut 2.5σ) written after
1000 steps of NVT equilibration at T=1.2. Your job is to **continue** the
simulation seamlessly in the NVE ensemble.

## Your Task

1. Write a continuation input that does `read_restart` on the provided
   restart file and runs **2000 more steps in NVE** (do **not** re-create
   velocities, do **not** apply a thermostat, do **not** reset the
   timestep — the run must continue from step 1000 to step 3000).
2. Use thermo output every 100 steps (`step temp pe`), so the continuation
   log shows 21 thermo lines from step 1000 to step 3000.
3. Keep `log.lammps` in `/workspace/` and write the final state with
   `write_data final.data` (in `/workspace/`).
4. Write `results.json` in the standard CompChemBench schema (LJ reduced
   units):

   ```json
   {
     "values": {
       "first_step": <int>,
       "first_pe": <float>,
       "final_step": <int>,
       "final_pe": <float>,
       "final_temp": <float>
     },
     "units": {
       "first_step": "1",
       "first_pe": "ε/atom",
       "final_step": "1",
       "final_pe": "ε/atom",
       "final_temp": "ε/kB"
     }
   }
   ```

   - `first_step` / `first_pe`: step and potential energy per atom of the
     **first** thermo line of the continuation (must be step 1000 — the
     continuation joins the equilibrated state seamlessly)
   - `final_step` / `final_pe` / `final_temp`: values at step 3000

## Requirements

- Parse the **actual** `log.lammps` — do not hardcode values. The verifier
  checks the log structure (banner, completion footer, exact thermo row
  count and step range), compares the continuation's first-step PE against
  the known equilibrated-state energy (proving the restart was read, not
  re-initialized), and **independently re-evaluates** the energy of
  `final.data` with a 0-step run, requiring it to match the log's last
  thermo line.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/equil.restart`
- Output: `log.lammps`, `final.data`, `results.json` in `/workspace/`

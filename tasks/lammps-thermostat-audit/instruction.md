# Task: Audit a Thermostat Setup (LAMMPS)

## Background

A colleague ran an NVT simulation of an LJ fluid (500 atoms, ρ*=0.8442,
target T*=1.2) and is uneasy: "the run finishes and the *average*
temperature looks about right, but I don't trust the setup — the fluid is
not being thermostatted correctly." Your job is to audit the input, find
what is wrong, fix it, and demonstrate a correctly thermostatted run.

## Your Task

`/workspace/assets/broken.in` contains the simulation in question (LJ
units, 5000 steps). Read it critically:

- Which atoms does the thermostat actually act on?
- Is the integration timestep appropriate for an LJ fluid at T*≈1.2?

1. Write a corrected input `fixed.in` in `/workspace/` that samples the
   **whole fluid** under NVT at T*=1.2 with a proper timestep, and runs
   the same 5000 steps with the same system (do not change the potential,
   the initial configuration protocol, or the velocity seed — only fix the
   thermostat and integration problems).
2. Run it so that `log.lammps` is written to `/workspace/`, with thermo
   output every 100 steps including `step temp pe`.
3. Dump the full state every 100 steps to `state.dump` in `/workspace/`:
   custom format with columns `id type x y z vx vy vz`.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "avg_temp": <float>,
       "final_step": <int>
     },
     "units": {
       "avg_temp": "ε/kB",
       "final_step": "1"
     }
   }
   ```

   - `avg_temp`: mean of the thermo temperature over the second half of
     the run (steps 2500–5000)
   - `final_step`: 5000

## Requirements

- Parse the **actual** run output — do not hardcode values. The verifier
  checks `fixed.in` (thermostat must act on **all** atoms at the target
  temperature; timestep must be in a sane range), checks the log structure
  and average temperature, and — as the decisive check — **independently
  recomputes the kinetic temperature from the velocities in `state.dump`
  and the potential energy from the positions in `state.dump`** (0-step
  LAMMPS re-evaluation), requiring both to match the thermo output. The
  trajectory must be real.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/broken.in`
- Output: `fixed.in`, `log.lammps`, `state.dump`, `results.json` in `/workspace/`

# Task: LJ Melt Simulation (LAMMPS)

## Background

Run a Lennard-Jones fluid simulation using LAMMPS and extract thermodynamic
properties from the output log.

## Your Task

A LAMMPS input file `lj_melt.in` is provided in `/workspace/assets/`.
Copy it to your working directory and run it with LAMMPS.

The simulation runs **5000 NVE steps** of a 3D Lennard-Jones fluid at
reduced units (ε=1, σ=1) starting from a random FCC arrangement.

After the run completes:

1. Parse the LAMMPS log file (`log.lammps`) to extract the **last** thermo
   output line.
2. Write `results.json` in the standard CompChemBench schema (values are in
   LJ reduced units):

   ```json
   {
     "values": {
       "final_step": <int>,
       "final_temp": <float>,
       "final_pe": <float>,
       "log_lines": <int>
     },
     "units": {
       "final_step": "1",
       "final_temp": "ε/kB",
       "final_pe": "ε/atom",
       "log_lines": "1"
     }
   }
   ```

   - `final_step`: the last timestep in the thermo output
   - `final_temp`: temperature at the last step
   - `final_pe`: potential energy per atom at the last step
   - `log_lines`: total number of lines in `log.lammps`

## Requirements

- Run LAMMPS with the provided input file (do not modify the input).
- Do **not** hardcode the thermodynamic values.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.
- The log file (`log.lammps`) must be the authentic LAMMPS output (must
  contain the LAMMPS version banner and "Total wall time" footer).

## Files

- Input: `/workspace/assets/lj_melt.in` (copy to `/workspace/` before running)
- Output: `log.lammps`, `results.json` in `/workspace/`

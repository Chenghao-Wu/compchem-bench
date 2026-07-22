# Task: Fix a Broken LAMMPS Input Script (LAMMPS)

## Background

A LAMMPS input script for a 3D Lennard-Jones fluid simulation fails to run.
It contains **exactly three errors**. Find and fix them, then run the
simulation to completion.

## Your Task

The file `/workspace/assets/broken.in` is intended to simulate a 3D
Lennard-Jones fluid (ε=1, σ=1, particle mass=1):

- FCC lattice at reduced density 0.8442, 5×5×5 unit cells (500 atoms)
- LJ pair potential with cutoff 2.5σ
- Initial temperature 1.2 (reduced units), **NVE** dynamics
- **1000 steps**, thermo output every 100 steps

The script as shipped does **not** run: it contains exactly three errors
(misspelled commands and a missing required setting). The comments and the
intended physics above tell you what the script is supposed to do.

1. Copy `broken.in` to your working directory, diagnose the errors, and
   produce a **fixed** input `fixed.in` in `/workspace/`.
2. Run LAMMPS with the fixed input so that `log.lammps` is written to
   `/workspace/`.
3. Write `results.json` in the standard CompChemBench schema (values are in
   LJ reduced units):

   ```json
   {
     "values": {
       "final_step": <int>,
       "final_temp": <float>,
       "final_pe": <float>
     },
     "units": {
       "final_step": "1",
       "final_temp": "ε/kB",
       "final_pe": "ε/atom"
     }
   }
   ```

## Requirements

- Do not change the physics of the intended run (system size, potential,
  seed, ensemble, run length, thermo interval). Only fix what is broken.
- Parse the **actual** `log.lammps` — do not hardcode thermodynamic values.
  The verifier checks the log for the LAMMPS banner and completion footer,
  the exact thermo row count and step range, the absence of ERROR lines,
  and that `results.json` matches the log.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/broken.in`
- Output: `fixed.in`, `log.lammps`, `results.json` in `/workspace/`

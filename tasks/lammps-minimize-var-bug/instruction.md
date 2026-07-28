# Task: A Minimisation Report That Says Nothing Happened (LAMMPS)

## Background

A LAMMPS input script can run to completion, exit cleanly, and still report
numbers that are simply not true. When the summary a script prints disagrees
with the run it just performed, the summary is the thing that is broken —
and trusting it silently corrupts everything downstream.

## Your Task

`/workspace/assets/` contains a conjugate-gradient energy minimisation of a
porphin molecule (C20H14N4, 40 atoms) with the GAFF2 force field:

- `porphin_minimize.in` — the input script
- `system_gaff2.data` — LAMMPS data file (topology + coordinates)
- `system_gaff2.in.settings` — GAFF2 coefficients

The script runs to completion without any LAMMPS error. But the summary it
prints at the end claims

```
  Energy Change:   0 kcal/mol
```

with an identical initial and final energy — even though the minimiser
plainly did work, and the script's own earlier output disagrees with its
final summary. **The dynamics are fine; the reporting is wrong.**

1. Copy the assets' input to `/workspace/`, run it, and study the log to
   work out why the reported energies are wrong.
2. Produce a corrected input `/workspace/porphin_minimize_fixed.in` that
   reports the **true** energies. Keep the physics byte-for-byte identical —
   same force-field styles, same `min_style cg`, same `minimize 1.0e-4
   1.0e-6 1000 10000` tolerances, same data file. Only the reporting logic
   may change.
3. Run the fixed input so its log is written to `/workspace/log.lammps` and
   the minimised structure to `/workspace/porphin_minimized.data`.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "e_initial": <float>,
       "e_final": <float>,
       "delta_e": <float>,
       "n_iterations": <int>
     },
     "units": {
       "e_initial": "kcal/mol",
       "e_final": "kcal/mol",
       "delta_e": "kcal/mol",
       "n_iterations": "1"
     }
   }
   ```

   - `e_initial` — potential energy of the structure as read from the data
     file, before any minimisation
   - `e_final` — potential energy after minimisation
   - `delta_e` — `e_final - e_initial` (negative: the minimiser lowers it)
   - `n_iterations` — number of minimisation iterations actually performed,
     i.e. the step count on the minimisation's `Loop time of ... for N steps
     with 40 atoms` line

## Requirements

- Leave the input's file references exactly as they are: your fixed script
  must still read `assets/system_gaff2.data` and include
  `assets/system_gaff2.in.settings` by those same relative paths, and must
  run from `/workspace/`. It should be a drop-in replacement for the
  original.
- Keep the three summary lines in exactly this format, with correct values:

  ```
    Initial Energy:  <value> kcal/mol
    Final Energy:    <value> kcal/mol
    Energy Change:   <value> kcal/mol
  ```

- **Fix the reporting mechanism, do not paper over it.** Substituting
  literal numbers you read out of a log is not a fix. The verifier re-runs
  *your* fixed input against a perturbed copy of the same molecule — one
  with different energies — and requires the summary your script prints to
  be correct for **that** system too. A script that prints constants fails
  this check.
- Parse the **actual** log for `results.json`. The verifier also validates
  the shipped assets by sha256, checks the log for a genuine minimisation
  run, and independently recomputes the potential energy of your
  `porphin_minimized.data` with the in-image LAMMPS to confirm it really is
  the minimised structure you reported.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/porphin_minimize.in`,
  `/workspace/assets/system_gaff2.data`,
  `/workspace/assets/system_gaff2.in.settings`
- Output: `porphin_minimize_fixed.in`, `log.lammps`,
  `porphin_minimized.data`, `results.json` in `/workspace/`

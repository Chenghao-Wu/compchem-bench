# Task: GFN2-xTB Geometry Optimization of Caffeine (xtb)

## Background

Run a GFN2-xTB geometry optimization of caffeine (C8H10N4O2) and report
the final total energy and the molecular dipole moment at the optimized
geometry.

## Your Task

The starting geometry `caffeine.xyz` is provided in `/workspace/assets/`.
Run xtb with the GFN2 Hamiltonian in optimization mode from `/workspace/`,
saving the full standard output to `xtb_opt.out`:

```bash
xtb caffeine.xyz --gfn 2 --opt > xtb_opt.out 2>&1
```

After the run completes:

1. Keep the optimized geometry `xtbopt.xyz` (written by xtb) in
   `/workspace/` — it is needed for verification.
2. Parse `xtb_opt.out` to extract:
   - the final total energy (the `TOTAL ENERGY` line of the last
     single-point evaluation at the optimized geometry)
   - the total molecular dipole moment (the `tot (Debye)` value from the
     `molecular dipole` block, `full:` line)
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, Eh>,
       "dipole_moment": <float, Debye>,
       "opt_converged": <bool>
     },
     "units": {
       "final_energy": "Eh",
       "dipole_moment": "Debye",
       "opt_converged": "1"
     }
   }
   ```

## Requirements

- Run the optimization to convergence — the log must contain
  `GEOMETRY OPTIMIZATION CONVERGED`.
- Do **not** hardcode the energy or dipole — the verifier runs its own
  single-point calculation on your `xtbopt.xyz` and requires it to agree
  with your log and your `results.json`.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/caffeine.xyz`
- Output: `xtb_opt.out`, `xtbopt.xyz`, `results.json` in `/workspace/`

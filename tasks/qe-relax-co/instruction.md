# Task: Plane-Wave DFT Geometry Relaxation of Carbon Monoxide (Quantum ESPRESSO)

## Background

Optimize the bond length of a CO molecule in a periodic box using Quantum
ESPRESSO `pw.x` (plane-wave DFT, PBE functional, BFGS ionic relaxation).

## Your Task

A complete `pw.x` input file `co_relax.in` is provided in `/workspace/assets/`,
together with the pseudopotentials it references in `/workspace/assets/pseudo/`.
Copy both into your working directory (the input expects the pseudopotential
directory at `./pseudo`) and run `pw.x` on the input **exactly as provided**.

After the run completes:

1. Keep the standard output as `co_relax.out` and keep the `outdir/` directory
   (it contains the XML summary `pwscf.xml`) in `/workspace/` — both are
   needed for verification.
2. Parse the output to extract:
   - The final C–O bond length (from the final `ATOMIC_POSITIONS` block, in Å)
   - The final total energy (`Final energy` line, in Ry)
   - Whether the BFGS relaxation converged
   - The number of BFGS steps
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, Ry>,
       "co_bond_length": <float, Å>,
       "relax_converged": <bool>,
       "n_bfgs_steps": <int>
     },
     "units": {
       "final_energy": "Ry",
       "co_bond_length": "Å",
       "relax_converged": "1",
       "n_bfgs_steps": "1"
     }
   }
   ```

## Requirements

- Run the provided input unmodified.
- Do **not** hardcode the energy or bond length — the verifier runs its own
  SCF single-point calculation on the final geometry from your log and
  requires your log, your `results.json`, and its recomputation to agree.
- The output must contain `bfgs converged in` to confirm relaxation
  convergence, and end with `JOB DONE.`.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/co_relax.in`
- Pseudopotentials: `/workspace/assets/pseudo/C.pbe-n-kjpaw_psl.1.0.0.UPF`,
  `/workspace/assets/pseudo/O.pbe-n-kjpaw_psl.1.0.0.UPF`
- Output: `co_relax.out`, `outdir/`, `results.json` in `/workspace/`

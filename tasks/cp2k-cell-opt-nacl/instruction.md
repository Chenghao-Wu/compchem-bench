# Task: DFT Cell Optimization of Rocksalt NaCl (CP2K)

## Background

Run a DFT cell optimization (CELL_OPT) of the 8-atom conventional cell of
rocksalt NaCl using CP2K with the PBE functional and DZVP-MOLOPT-SR-GTH
basis set, and report the equilibrium lattice constant.

## Your Task

A CP2K input file `nacl_cellopt.inp` is provided in `/workspace/assets/`.
It describes the 8-atom conventional rocksalt cell (4 Na + 4 Cl) starting
from a slightly compressed lattice at the Γ point. Copy it to your working
directory and run CP2K. The basis-set and pseudopotential data files
(`BASIS_MOLOPT`, `GTH_POTENTIALS`) are part of the CP2K installation at
`/opt/cp2k/data/` — copy or symlink them into your working directory (the
input references them by bare filename).

After the run completes:

1. Keep the trajectory file `nacl_cellopt-pos-1.xyz` (written by CP2K) in
   `/workspace/` — it is needed for verification.
2. Parse the CP2K output to extract:
   - The final total energy at the last optimization step
   - The equilibrium lattice constant a0 (the optimized cell is cubic;
     use the final cell magnitude, e.g. from the last `CELL| Vector`
     block)
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, Ha>,
       "lattice_constant": <float, Å>,
       "cell_opt_converged": <bool>,
       "n_opt_steps": <int>
     },
     "units": {
       "final_energy": "Ha",
       "lattice_constant": "Å",
       "cell_opt_converged": "1",
       "n_opt_steps": "1"
     }
   }
   ```

## Requirements

- Run CP2K with the provided input (do not modify it).
- Do **not** hardcode the energy or lattice constant — the verifier runs
  its own single-point calculation on the final geometry from your
  trajectory with the final cell from your log, and requires your log,
  your `results.json`, and its recomputation to agree.
- The output must contain `GEOMETRY OPTIMIZATION COMPLETED` to confirm
  convergence.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/nacl_cellopt.inp`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `nacl_cellopt.out`, `nacl_cellopt-pos-1.xyz`, `results.json` in `/workspace/`

# Task: DFT Geometry Optimization of Ammonia (CP2K)

## Background

Run a DFT geometry optimization of ammonia (NH3) using CP2K with the PBE
functional and DZVP-MOLOPT-SR-GTH basis set.

## Your Task

A CP2K input file `nh3_geoopt.inp` is provided in `/workspace/assets/`.
Copy it to your working directory and run CP2K. The basis-set and
pseudopotential data files (`BASIS_MOLOPT`, `GTH_POTENTIALS`) are part of
the CP2K installation at `/opt/cp2k/data/` — copy or symlink them into your
working directory (the input references them by bare filename).

After the run completes:

1. Keep the trajectory file `nh3_geoopt-pos-1.xyz` (written by CP2K) in
   `/workspace/` — it is needed for verification.
2. Parse the CP2K output to extract:
   - The final total energy at the last geometry step
   - The N–H bond length at the optimized geometry (any of the three N–H bonds)
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, Ha>,
       "nh_bond_length": <float, Å>,
       "geo_opt_converged": <bool>,
       "n_geo_steps": <int>
     },
     "units": {
       "final_energy": "Ha",
       "nh_bond_length": "Å",
       "geo_opt_converged": "1",
       "n_geo_steps": "1"
     }
   }
   ```

## Requirements

- Run CP2K with the provided input (do not modify it).
- Do **not** hardcode the energy or bond length — the verifier runs its own
  single-point calculation on the final geometry from your trajectory and
  requires your log, your `results.json`, and its recomputation to agree.
- The output must contain `GEOMETRY OPTIMIZATION COMPLETED` to confirm
  convergence.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/nh3_geoopt.inp`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `nh3_geoopt.out`, `nh3_geoopt-pos-1.xyz`, `results.json` in `/workspace/`

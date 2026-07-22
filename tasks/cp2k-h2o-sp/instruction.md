# Task: DFT Single-Point Energy of Water (CP2K)

## Background

Run a single-point DFT energy calculation on a water molecule using CP2K
with the PBE functional and DZVP-MOLOPT-SR-GTH basis set.

## Your Task

A CP2K input file `h2o_sp.inp` is provided in `/workspace/assets/`. Copy it
to your working directory and run CP2K. The basis-set and pseudopotential
data files (`BASIS_MOLOPT`, `GTH_POTENTIALS`) are part of the CP2K
installation at `/opt/cp2k/data/` — copy or symlink them into your working
directory (the input references them by bare filename).

After the run completes:

1. Parse the CP2K output to extract the final total energy.
2. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "total_energy": <float, Ha>,
       "scf_converged": <bool>,
       "n_scf_steps": <int>
     },
     "units": {
       "total_energy": "Ha",
       "scf_converged": "1",
       "n_scf_steps": "1"
     }
   }
   ```

## Requirements

- Run CP2K with the provided input (do not modify it).
- Do **not** hardcode the energy value — the verifier reruns the identical
  single-point itself and requires your log, your `results.json`, and its
  own recomputation to agree.
- The output file must contain the CP2K version banner and the normal
  termination marker (`PROGRAM ENDED AT`).
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/h2o_sp.inp` (copy to `/workspace/`)
- Basis/pseudopotentials: `/opt/cp2k/data/BASIS_MOLOPT`,
  `/opt/cp2k/data/GTH_POTENTIALS`
- Output: `h2o_sp.out`, `results.json` in `/workspace/`

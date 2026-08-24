# Task: Geometry Optimization of NO2 (CP2K)

## Background

A CP2K input for a geometry optimization of the NO2 molecule (PBE /
DZVP-MOLOPT-GTH / GTH-PBE, non-periodic 10 Å box) has been prepared at
`/workspace/assets/no2_geoopt.inp`. Run the calculation to a converged
geometry and report the converged total energy.

The basis-set and pseudopotential data files are part of the CP2K
installation at `/opt/cp2k/data/`; the input references them by bare
filename.

## Your Task

1. Run the geometry optimization so the output `no2_geoopt.out` is written
   to `/workspace/`.
2. Save the input used for the reported run as `final.inp` in `/workspace/`.
3. Write `results.json` in the standard CompChemBench schema with the
   converged energy of the optimized geometry:

   ```json
   {
     "values": {
       "total_energy": <float, Ha>,
       "geoopt_converged": <bool>
     },
     "units": {
       "total_energy": "Ha",
       "geoopt_converged": "1"
     }
   }
   ```

## Requirements

- The intended calculation is the one described above: neutral NO2, its
  geometry, functional, basis, pseudopotentials, cutoffs, box, and GEO_OPT
  convergence thresholds. If the input needs correction to run validly and
  converge, change only what is needed and keep the intended settings
  unchanged.
- Parse the **actual** CP2K output — do not hardcode the energy. The
  verifier checks the output for SCF convergence, geometry-optimization
  completion, and normal termination; inspects `final.inp`; and requires
  the energy in `results.json` to match both the log and the calibrated
  reference.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/no2_geoopt.inp`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `final.inp`, `no2_geoopt.out`, `results.json` in `/workspace/`

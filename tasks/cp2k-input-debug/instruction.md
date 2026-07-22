# Task: Fix a Broken CP2K Input File (CP2K)

## Background

A CP2K input file for a single-point DFT energy calculation of methane
(CH4) fails to run correctly. It contains **exactly three errors**. Find
and fix them, then run the calculation to completion.

## Your Task

The file `/workspace/assets/broken_ch4_sp.inp` is intended to compute the
single-point energy of methane with:

- PBE functional, `DZVP-MOLOPT-SR-GTH` basis, `GTH-PBE` pseudopotentials
- plane-wave cutoff **300 Ha** (Hartree; CP2K's default energy unit) with
  `REL_CUTOFF 60`
- a 10 Å cubic non-periodic box
- `EPS_SCF 1.0E-7`, `SCF_GUESS ATOMIC`

The header comment in the input also records these intended settings.

The input as shipped does **not** produce the intended calculation: it
contains exactly three errors — a missing section terminator, a misspelled
basis-set name, and a wrong unit on the cutoff. Not all of them stop the
parser; one of them lets the run finish with a physically meaningless
result.

1. Copy `broken_ch4_sp.inp` to your working directory, diagnose the three
   errors, and produce a **fixed** input `fixed.inp` in `/workspace/`.
2. The basis-set and pseudopotential data files (`BASIS_MOLOPT`,
   `GTH_POTENTIALS`) are part of the CP2K installation at `/opt/cp2k/data/`
   — copy or symlink them into your working directory (the input references
   them by bare filename).
3. Run CP2K with the fixed input so that the output `ch4_sp.out` is written
   to `/workspace/` (run from `/workspace` with `PROJECT ch4_sp`
   unchanged, or pass `-o ch4_sp.out`).
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "total_energy": <float, Ha>,
       "scf_converged": <bool>
     },
     "units": {
       "total_energy": "Ha",
       "scf_converged": "1"
     }
   }
   ```

## Requirements

- Do not change the physics of the intended run (geometry, functional,
  basis, pseudopotentials, cutoff value in Hartree, box, SCF settings).
  Only fix what is broken.
- Parse the **actual** CP2K output — do not hardcode the energy. The
  verifier checks the output for the CP2K banner, SCF convergence, and
  normal termination, inspects your `fixed.inp` for the three repairs, and
  requires the energy in `results.json` to match both the log and the
  calibrated reference.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/broken_ch4_sp.inp`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `fixed.inp`, `ch4_sp.out`, `results.json` in `/workspace/`

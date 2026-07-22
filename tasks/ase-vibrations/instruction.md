# Task: Finite-Displacement Vibrational Analysis of a Cu4 Cluster (ASE/EMT)

## Background

Vibrational analysis via finite displacements characterizes a stationary
point: a true minimum has no imaginary vibrational modes. Perform such an
analysis for a small copper cluster with the EMT potential.

## Your Task

1. Build a **tetrahedral Cu4 cluster** (non-periodic; a slightly perturbed
   tetrahedron with edges around 2.6 Å is a fine starting guess) and attach
   an `EMT()` calculator.
2. Optimize the geometry (e.g. `ase.optimize.BFGS`) until the maximum force
   on any atom is below **0.01 eV/Å**. Write the optimized structure to
   `optimized.xyz`.
3. Run a finite-displacement vibrational analysis
   (`ase.vibrations.Vibrations`, default displacement, cache name `vib`)
   on the optimized structure, keeping the cache directory `vib/` in your
   working directory.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_modes": <int>,
       "n_imaginary": <int>,
       "freq_1": <float, cm^-1>, "freq_2": <float, cm^-1>,
       "freq_3": <float, cm^-1>, "freq_4": <float, cm^-1>,
       "freq_5": <float, cm^-1>, "freq_6": <float, cm^-1>
     },
     "units": {
       "n_modes": "1",
       "n_imaginary": "1",
       "freq_1": "cm^-1", "freq_2": "cm^-1",
       "freq_3": "cm^-1", "freq_4": "cm^-1",
       "freq_5": "cm^-1", "freq_6": "cm^-1"
     }
   }
   ```

   - `n_modes`: total number of normal modes (3N)
   - `n_imaginary`: number of modes with a significant imaginary frequency
     (|Im ν| > 10 cm⁻¹; near-zero acoustic noise does not count)
   - `freq_1` … `freq_6`: the **six vibrational** frequencies of the
     cluster (the 3N−6 = 6 non-acoustic modes), sorted ascending, in cm⁻¹

## Requirements

- The optimized structure must be a genuine force minimum of the EMT
  potential — the verifier recomputes its forces.
- The verifier reloads your `vib/` cache **and** independently reruns the
  full displacement analysis from your `optimized.xyz`; frequencies are
  checked three ways (reported ≡ cache ≡ rerun ≡ calibrated reference).
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

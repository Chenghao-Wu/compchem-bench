# Task: NEB Barrier for an Adatom Hop on Cu(100) (ASE/EMT)

## Background

The nudged elastic band (NEB) method finds minimum-energy paths and
migration barriers. Compute the barrier for a Cu adatom hopping between two
adjacent hollow sites on Cu(100) with the EMT potential.

## Your Task

Two **relaxed** endpoint structures are provided:

- `/workspace/assets/initial.xyz` — adatom at hollow site A
- `/workspace/assets/final.xyz` — adatom at the adjacent hollow site B

1. Build a band of **7 images** (the two provided endpoints + 5
   interpolated intermediate images) and attach an `EMT()` calculator to
   every image.
2. Run NEB (`ase.mep.NEB`) with the **climbing image** enabled and optimize
   the band until the maximum force on the climbing image is below
   **0.05 eV/Å**.
3. Write the final band (all 7 frames, endpoints included, in order) to
   `neb_band.traj`.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "barrier": <float, eV>,
       "n_images": <int>,
       "saddle_fmax": <float, eV/Å>
     },
     "units": {
       "barrier": "eV",
       "n_images": "1",
       "saddle_fmax": "eV/Å"
     }
   }
   ```

   - `barrier`: migration barrier = (highest image energy) − (initial
     endpoint energy), in eV
   - `saddle_fmax`: maximum force magnitude on the highest-energy image
     after convergence

## Requirements

- The two endpoint frames of your band must reproduce the provided
  structures (you may re-relax them slightly, but not substitute different
  structures).
- The verifier recomputes the energy of **every frame** with EMT: the
  barrier is derived from your band's own geometries, the highest-energy
  frame must be an interior image whose recomputed forces show a converged
  saddle point, and the two endpoints must be degenerate in energy.
  A band that was never optimized (e.g. raw interpolation) fails the force
  check even if its energies are reported truthfully.
- Do not modify files under `/workspace/assets`.
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

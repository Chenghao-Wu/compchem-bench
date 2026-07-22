# Task: NVT MD and Radial Distribution Function (LAMMPS)

## Background

Run an NVT Lennard-Jones fluid simulation in LAMMPS, compute the radial
distribution function (RDF), and extract the first-peak position and height.

## Your Task

A LAMMPS input file `nvt_rdf.in` is provided in `/workspace/assets/`.
Copy it to your working directory and run it with LAMMPS.

The simulation:
- Equilibrates a LJ fluid under NVT (Nosé-Hoover thermostat) for 2000 steps
- Collects RDF data over 3000 production steps into `rdf.dat`

After the run completes:

1. Keep all run products in `/workspace/`: `log.lammps`, `rdf.dat`, and
   `final.data` (written by the input's `write_data` command).
2. Parse `rdf.dat` to find the **first peak** of g(r): the maximum g(r)
   value at r > 0.5σ.
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "first_peak_r": <float, σ>,
       "first_peak_gr": <float>,
       "n_rdf_bins": <int>
     },
     "units": {
       "first_peak_r": "σ",
       "first_peak_gr": "1",
       "n_rdf_bins": "1"
     }
   }
   ```

## Requirements

- Run LAMMPS with the provided input (do not modify it).
- Parse the **actual** `rdf.dat` output — do not hardcode values. The
  verifier checks that the log contains both run segments (equilibration
  and production) with the correct thermo row counts, that `final.data`
  contains the full system, that `rdf.dat` has the expected bin grid, and
  it independently re-evaluates the energy of `final.data` to confirm the
  files are genuine products of the run.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.
- The log (`log.lammps`) must contain LAMMPS banner and completion footer.

## Files

- Input: `/workspace/assets/nvt_rdf.in` (copy to `/workspace/`)
- Output: `log.lammps`, `rdf.dat`, `final.data`, `results.json` in `/workspace/`

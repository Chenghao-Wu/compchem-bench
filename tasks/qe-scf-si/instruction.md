# Task: Plane-Wave DFT SCF of Crystalline Silicon (Quantum ESPRESSO)

## Background

Run a self-consistent field (SCF) total-energy calculation of silicon in the
diamond structure with Quantum ESPRESSO `pw.x` (plane-wave DFT, PBE
functional).

## Your Task

A complete `pw.x` input file `si_scf.in` is provided in `/workspace/assets/`,
together with the pseudopotential it references in `/workspace/assets/pseudo/`.
Copy both into your working directory (the input expects the pseudopotential
directory at `./pseudo`) and run `pw.x` on the input **exactly as provided**.

After the run completes:

1. Keep the standard output as `si_scf.out` and keep the `outdir/` directory
   (it contains the XML summary `pwscf.xml`) in `/workspace/` — both are
   needed for verification.
2. Parse the output to extract:
   - The converged total energy (the `!    total energy` line, in Ry)
   - Whether the SCF cycle converged
   - The number of SCF iterations
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "total_energy": <float, Ry>,
       "scf_converged": <bool>,
       "n_scf_iterations": <int>
     },
     "units": {
       "total_energy": "Ry",
       "scf_converged": "1",
       "n_scf_iterations": "1"
     }
   }
   ```

## Requirements

- Run the provided input unmodified (fixed plane-wave cutoff and k-point
  grid are part of the task).
- Do **not** hardcode the energy — the verifier cross-checks your standard
  output against the XML data file and against an independently calibrated
  reference value.
- The output must end with `JOB DONE.` and report `convergence has been
  achieved`.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/si_scf.in`
- Pseudopotential: `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- Output: `si_scf.out`, `outdir/`, `results.json` in `/workspace/`

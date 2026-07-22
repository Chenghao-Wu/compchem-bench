# Task: Diagnose and Fix Three Failing pw.x Runs (Quantum ESPRESSO)

## Background

A large part of practical DFT work is reading error logs and fixing broken
inputs. This task gives you three real failed `pw.x` runs — each with a
different class of problem — and asks you to diagnose, fix, and re-run every
one of them to a clean, converged finish.

## Your Task

Under `/workspace/assets/` you will find three case directories, each with a
broken input file and the captured output of the failed run:

| Case | Directory | Input | Failed log |
|------|-----------|-------|------------|
| 1 | `/workspace/assets/case1_pseudo/` | `case1.in` | `failed_run.out` |
| 2 | `/workspace/assets/case2_cell/` | `case2.in` | `failed_run.out` |
| 3 | `/workspace/assets/case3_scf/` | `case3.in` | `failed_run.out` |

Each directory also has a `pseudo/` folder with the pseudopotentials to use.

For **each** case:

1. Read the failed log, diagnose the problem (a missing/wrong resource
   reference, a contradictory cell definition, and an SCF convergence
   failure that needs the mixing/smearing strategy adjusted — one problem
   per case).
2. Write a fixed input as `/workspace/caseN/caseN.in` (N = 1, 2, 3),
   copying whatever pseudopotentials you need into `/workspace/caseN/`.
   The fixed calculation must describe the **same physical system with the
   same numerical settings** (cell, atoms, `ecutwfc`, `ecutrho`, k-points,
   `conv_thr`) as the broken input — fix the problem, don't weaken the
   calculation.
3. Actually run it with `pw.x` and keep the full log as
   `/workspace/caseN/caseN.out`. The run must converge
   (`convergence has been achieved`) and end with `JOB DONE.`.

Then write `results.json` in the standard CompChemBench schema with the
converged total energy of each fixed run:

```json
{
  "values": {
    "case1_energy_Ry": <float>,
    "case2_energy_Ry": <float>,
    "case3_energy_Ry": <float>
  },
  "units": {
    "case1_energy_Ry": "Ry",
    "case2_energy_Ry": "Ry",
    "case3_energy_Ry": "Ry"
  }
}
```

## Requirements

- Each `caseN.out` must be a genuine, complete `pw.x` log produced from your
  fixed input in this environment — the verifier checks the version banner,
  the settings echoes (which must match the required system and cutoffs),
  SCF convergence, and `JOB DONE.`, and compares each converged energy
  against independently calibrated references.
- Do not change the system (cell, atom species/positions) or lower
  `ecutwfc`/`ecutrho`/k-points below what each broken input specifies.
- The fixed inputs must parse as valid `pw.x` inputs and use the provided
  pseudopotentials (byte-identical to the ones shipped in each case's
  `pseudo/` directory).

## Files

- Broken inputs + failed logs: `/workspace/assets/case{1_pseudo,2_cell,3_scf}/`
- Output: `/workspace/case{1,2,3}/case{1,2,3}.in`,
  `/workspace/case{1,2,3}/case{1,2,3}.out`, and `/workspace/results.json`

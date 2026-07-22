# Task: Plane-Wave Cutoff Convergence for Silicon (Quantum ESPRESSO)

## Background

Every plane-wave DFT calculation requires a convergence test of the
kinetic-energy cutoff `ecutwfc`: the total energy must be stationary with
respect to the cutoff before any derived quantity can be trusted. The
standard criterion is that the change in total energy between successive
cutoffs falls below a threshold per atom (here: 1 meV/atom).

## Your Task

Run a series of **five real `pw.x` SCF calculations** of crystalline silicon
(diamond structure, 2-atom primitive cell, `ibrav = 2` with
`celldm(1) = 10.26`, Si at alat coordinates (0,0,0) and (1/4,1/4,1/4)) with:

- `ecutwfc` = 20, 30, 40, 50, 60 Ry (one run per cutoff)
- `ecutrho` **fixed at 480 Ry** for all five runs (only the wavefunction
  cutoff varies)
- `conv_thr = 1.0d-10`
- k-points: `K_POINTS automatic` with a `4 4 4 1 1 1` Monkhorst–Pack grid
- the provided pseudopotential `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`

Keep the standard output of each run as `si_ecut20.out`, `si_ecut30.out`,
`si_ecut40.out`, `si_ecut50.out`, `si_ecut60.out` in `/workspace/` (each must
be a complete, unmodified `pw.x` log ending with `JOB DONE.`).

Then determine the **converged cutoff**: the smallest `ecutwfc` for which the
total-energy change from the previous cutoff, **per atom**, drops below
1 meV/atom.

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "ecutwfc_grid": [20.0, 30.0, 40.0, 50.0, 60.0],
    "total_energies": [<float, Ry>, ...],
    "converged_ecutwfc": <float, Ry>,
    "criterion_meV_per_atom": 1.0
  },
  "units": {
    "ecutwfc_grid": "Ry",
    "total_energies": "Ry",
    "converged_ecutwfc": "Ry",
    "criterion_meV_per_atom": "meV/atom"
  }
}
```

`total_energies[i]` must be the converged `! total energy` of the run at
`ecutwfc_grid[i]`.

## Requirements

- All five runs must actually be performed with the settings above — the
  verifier inspects every log (version banner, SCF iteration table, cutoff
  echoes, convergence, `JOB DONE.`), cross-checks each log against your
  `results.json`, and **independently re-runs the lowest-cutoff point** to
  confirm your numbers are real.
- Do not weaken `conv_thr`, `ecutrho`, or the k-grid; the settings echoed in
  each log must match the required values.
- The converged cutoff must follow from your own energy table via the
  1 meV/atom rule — the verifier re-derives it from your table.

## Files

- Pseudopotential: `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- Output: `si_ecut{20,30,40,50,60}.out` and `results.json` in `/workspace/`

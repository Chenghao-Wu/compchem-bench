# Task: Dihedral Potential-Energy Profile of n-Hexane

Determine the torsional potential-energy profile of n-hexane about the central C3–C4 bond using Quantum ESPRESSO.

A relaxed all-anti geometry is provided at:

`/workspace/assets/hexane_anti.xyz`

The atom order is C1–C6 followed by the 14 H atoms. The provided structure corresponds to the C2–C3–C4–C5 anti configuration. Pseudopotentials are available in:

`/workspace/assets/pseudo/`

Evaluate the seven conformations

`0, 30, 60, 90, 120, 150, 180 degrees`

by rigidly rotating the C4-side fragment (atoms 4–6 and 14–20) around the C3–C4 bond. Preserve all other internal coordinates and the original atom ordering and cell placement.

For every conformation, perform a Quantum ESPRESSO `pw.x` SCF calculation using:

* PBE
* `ibrav = 1`
* `celldm(1) = 30`
* `ecutwfc = 50 Ry`
* `ecutrho = 400 Ry`
* fixed occupations
* `conv_thr = 1.0d-9`
* Gamma-point sampling
* the supplied C and H pseudopotentials

Do not relax the scan geometries.

Store each calculation under:

`/workspace/scan/phi_PPP/`

with its input as `pw.in` and complete output as `pw.out`.

Use zero-padded names:

`phi_000`, `phi_030`, `phi_060`, `phi_090`, `phi_120`, `phi_150`, `phi_180`.

## Deliverable

Write `/workspace/results.json`:

```json
{
  "values": {
    "dihedral_grid_deg": [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0],
    "total_energies_Ry": [<float>, "..."],
    "relative_energies_kcal_mol": [<float>, "..."],
    "syn_barrier_kcal_mol": <float>,
    "gauche_energy_kcal_mol": <float>,
    "eclipsed_barrier_kcal_mol": <float>
  },
  "units": {
    "dihedral_grid_deg": "deg",
    "total_energies_Ry": "Ry",
    "relative_energies_kcal_mol": "kcal/mol",
    "syn_barrier_kcal_mol": "kcal/mol",
    "gauche_energy_kcal_mol": "kcal/mol",
    "eclipsed_barrier_kcal_mol": "kcal/mol"
  }
}
```

Use the 180° structure as the zero of energy and convert Ry to kcal/mol using:

`syn_barrier_kcal_mol`, `gauche_energy_kcal_mol`, and `eclipsed_barrier_kcal_mol` are the relative energies at 0°, 60°, and 120°, respectively.

## Requirements

* All seven SCF calculations must actually be executed.
* The geometries must form a rigid scan of the supplied structure.
* Do not alter the specified electronic-structure settings or relax the geometries.
* Derive all reported energies from the actual `pw.x` outputs; do not hardcode reference values.
* Every calculation must converge normally and its output must end with `JOB DONE.`
* `results.json` must be valid and internally consistent.

The verifier checks the scan geometries, bond-length preservation, SCF convergence, output integrity, reported energies, and independently reruns selected scan points.

Do not use online solutions or task-specific hints.

## Files

Input:

* `/workspace/assets/hexane_anti.xyz`
* `/workspace/assets/pseudo/C.pbe-n-kjpaw_psl.1.0.0.UPF`
* `/workspace/assets/pseudo/H.pbe-rrkjus_psl.1.0.0.UPF`

Output:

* `/workspace/scan/phi_PPP/pw.in`
* `/workspace/scan/phi_PPP/pw.out`
* `/workspace/results.json`

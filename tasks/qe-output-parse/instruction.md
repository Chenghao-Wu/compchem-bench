# Task: Parse a Real Quantum ESPRESSO pw.x Output

## Background

A real `pw.x` SCF calculation (2-atom silicon cell, PBE, plane-wave DFT) was
run inside this very image, and its raw artifacts are provided. Your job is
to extract the key physical quantities from them — a routine post-processing
task in computational chemistry.

## Your Task

The directory `/workspace/assets/sample_run/` contains:

- `si_sample.out` — the standard output of a converged `pw.x` SCF run
- `pwscf.xml` — the XML data file written by the same run

Parse these files and extract:

- The converged total energy (Ry)
- The total force on the system (the `Total force` line, Ry/bohr)
- The Fermi energy (eV)

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "final_energy": <float, Ry>,
    "total_force": <float, Ry/bohr>,
    "fermi_energy": <float, eV>
  },
  "units": {
    "final_energy": "Ry",
    "total_force": "Ry/bohr",
    "fermi_energy": "eV"
  }
}
```

## Requirements

- The values must come from the provided artifacts. Do **not** modify the
  files in `/workspace/assets/` — the verifier checks their integrity by
  cryptographic hash before doing anything else, and re-parses them
  independently for comparison against your `results.json`.
- Note the XML file stores energies in Hartree atomic units while the text
  output uses Rydberg — convert consistently if you use both sources.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/sample_run/si_sample.out`,
  `/workspace/assets/sample_run/pwscf.xml`
- Output: `results.json` in `/workspace/`

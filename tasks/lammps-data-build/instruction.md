# Task: Build a LAMMPS Data File for Bulk Cu (LAMMPS)

## Background

LAMMPS simulations start from a **data file** describing the simulation box,
atom types, masses, and coordinates. Given a structure file, produce a data
file that LAMMPS can actually simulate.

## Your Task

`/workspace/assets/cu_fcc.xyz` contains a 3×3×3 FCC Cu supercell (extended
XYZ format, with the cell in the `Lattice=` comment). Convert it into a
LAMMPS data file `cu.data` in `/workspace/` with these exact conventions:

- `units metal`, `atom_style atomic` (data file lines: `id type x y z`)
- **one** atom type (all Cu)
- Masses section: Cu atomic mass **63.546** amu
- Simulation box matching the XYZ cell exactly, origin at (0, 0, 0)
- All atoms from the XYZ file, same positions

Also write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "n_atoms": <int>,
    "n_types": <int>,
    "mass_cu": <float>,
    "box_len": <float>
  },
  "units": {
    "n_atoms": "1",
    "n_types": "1",
    "mass_cu": "amu",
    "box_len": "Å"
  }
}
```

## Requirements

- The data file must be **simulatable**, not just textually plausible: the
  verifier loads it with LAMMPS itself (`read_data` + `run 0`) using the
  provided EAM potential `/workspace/assets/Cu_mishin1.eam.alloy` and checks
  the initial energy against the known cohesive energy of FCC Cu. A file
  that LAMMPS cannot read, or whose structure only approximately matches
  the XYZ (e.g. a hand-rolled lattice with a rounded lattice constant),
  fails.
- Do not modify the files in `/workspace/assets/` — the verifier pins them
  by sha256.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/cu_fcc.xyz`, `/workspace/assets/Cu_mishin1.eam.alloy`
- Output: `cu.data`, `results.json` in `/workspace/`

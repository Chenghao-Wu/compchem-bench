# Task: Convert a CIF to extxyz and LAMMPS data (ASE)

## Background

Simulation pipelines chain formats: crystallographic CIF → analysis formats
(extxyz) → MD engine inputs (LAMMPS data). Convert a provided structure
faithfully — the conversion must preserve cell, species, and positions, and
the LAMMPS data file must be parseable by LAMMPS itself.

## Your Task

The input structure is `/workspace/assets/nacl.cif` (rocksalt NaCl,
conventional cubic cell, 8 atoms, lattice parameter `a = 5.6402` angstrom).

1. Read the CIF (e.g. `ase.io.read`).
2. Write the structure to `nacl.extxyz` (extended XYZ, cell included).
3. Write the structure to `nacl.data` in **LAMMPS data format**
   (`atom_style atomic`, e.g. `ase.io.write(..., format="lammps-data")`).
   Atom types must be integers with a documented element↔type mapping.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_atoms": <int>,
       "n_types": <int>,
       "type_na": <int>,
       "type_cl": <int>
     },
     "units": {
       "n_atoms": "1",
       "n_types": "1",
       "type_na": "1",
       "type_cl": "1"
     }
   }
   ```

   - `type_na` / `type_cl`: the integer atom type assigned to Na / Cl in
     `nacl.data` (must match the file's Masses section)

## Requirements

- Both output files must describe the **same structure as the CIF**: same
  cell (to 1e-4 Å), same species, same positions (to 1e-4 in fractional
  coordinates, modulo lattice translations).
- The verifier additionally loads `nacl.data` with the **LAMMPS engine
  itself** (`read_data` + `run 0`) — a file LAMMPS cannot parse is a fail,
  even if ASE can read it.
- Do not modify files under `/workspace/assets`.
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

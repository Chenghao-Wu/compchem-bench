# Task: Build an fcc Cu Supercell (ASE)

## Background

Structure preparation is the first step of any simulation. Use ASE to
construct a face-centered cubic (fcc) copper supercell programmatically —
do not download or hand-write coordinates.

## Your Task

1. Build the **conventional cubic fcc Cu cell** with lattice constant
   `a = 3.615` (angstrom), then repeat it **4 × 4 × 4** along the three
   cubic axes. (Hint: `ase.build.bulk(..., cubic=True)` plus `.repeat()`,
   or an equivalent construction.)
2. The resulting structure must contain **256 Cu atoms** in an orthogonal
   cell with the cell origin at (0, 0, 0).
3. Write the structure to `cu_supercell.xyz` in your working directory, in
   extended XYZ format **including the cell** (e.g. `ase.io.write` with
   `format="extxyz"`).
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_atoms": <int>,
       "lattice_constant": <float, Å>,
       "cell_length": <float, Å>
     },
     "units": {
       "n_atoms": "1",
       "lattice_constant": "Å",
       "cell_length": "Å"
     }
   }
   ```

   - `n_atoms`: total number of atoms in the supercell
   - `lattice_constant`: the fcc lattice constant `a` used
   - `cell_length`: the edge length of the cubic supercell

## Requirements

- Use ASE (already installed) to construct the structure in code.
- The structure must be a genuine fcc lattice: the verifier checks the
  nearest-neighbor distance and the 12-fold coordination of every atom,
  not just the atom count and cell.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

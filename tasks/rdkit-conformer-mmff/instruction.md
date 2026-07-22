# Task: Conformer Generation and MMFF Optimization (RDKit)

## Background

Generating a 3D conformer and relaxing it with a molecular mechanics force
field is a standard first step in many cheminformatics/compchem workflows.
Here you will do this for **ibuprofen** with RDKit's ETKDG embedder and the
MMFF94 force field.

## Your Task

The file `/workspace/assets/target.smi` contains the target molecule's
SMILES. Using RDKit (already installed):

1. Parse the SMILES and add explicit hydrogens (`Chem.AddHs`).
2. Embed **one** 3D conformer with ETKDG, using **exactly**
   `randomSeed = 0xf00d` (61453) so the result is reproducible:

   ```python
   params = AllChem.ETKDGv3()
   params.randomSeed = 0xf00d
   AllChem.EmbedMolecule(mol, params)
   ```

3. Optimize the conformer with the **MMFF94** force field
   (`AllChem.MMFFOptimizeMolecule`) until convergence.
4. Write the optimized molecule (with 3D coordinates) to `conformer.sdf`
   in `/workspace/`.
5. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "mmff_energy": <float, kcal/mol>,
       "n_rotatable_bonds": <int>,
       "n_heavy_atoms": <int>
     },
     "units": {
       "mmff_energy": "kcal/mol",
       "n_rotatable_bonds": "1",
       "n_heavy_atoms": "1"
     }
   }
   ```

   - `mmff_energy`: MMFF94 energy of the **optimized** conformer
   - `n_rotatable_bonds`: `Descriptors.NumRotatableBonds` of the molecule
   - `n_heavy_atoms`: number of heavy (non-hydrogen) atoms

## Requirements

- Use **exactly** the embedder and seed above, and MMFF94 for the
  optimization — do not substitute UFF or a different seed.
- Do **not** hardcode the energy. The verifier independently:
  (a) recomputes the MMFF energy of your submitted conformer,
  (b) re-optimizes it to confirm it is a true MMFF minimum, and
  (c) regenerates the reference conformer from the pinned seed.
  Fabricated or un-optimized structures are rejected.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/target.smi`
- Output: `conformer.sdf`, `results.json` in `/workspace/`

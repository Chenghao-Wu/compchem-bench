# Task: Canonicalize SMILES with RDKit

## Background

SMILES strings are not unique: the same molecule can be written many
equivalent ways. RDKit produces a well-defined **canonical SMILES** for a
molecule, which is the standard way to deduplicate and compare structures.

## Your Task

The file `/workspace/assets/input_smiles.txt` contains one (non-canonical)
SMILES per line. Using RDKit (already installed in your environment):

1. Parse every line with RDKit.
2. Write `canonical.smi` in `/workspace/`: for each input line, in the
   **same order**, the canonical **isomeric** SMILES
   (`Chem.MolToSmiles(Chem.MolFromSmiles(s))`, default settings).
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_input": <int>,
       "n_valid": <int>,
       "n_unique": <int>
     },
     "units": {
       "n_input": "1",
       "n_valid": "1",
       "n_unique": "1"
     }
   }
   ```

   - `n_input`: number of lines in the input file
   - `n_valid`: number of lines that RDKit parses successfully
   - `n_unique`: number of **distinct** canonical SMILES among the valid
     molecules

## Requirements

- Use RDKit's canonicalization — do **not** attempt to canonicalize by
  hand or hardcode the outputs. The verifier recomputes the canonical
  SMILES of every input line with RDKit and compares them exactly,
  line by line.
- `canonical.smi` must have exactly one entry per valid input line, in
  input order.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/input_smiles.txt`
- Output: `canonical.smi`, `results.json` in `/workspace/`

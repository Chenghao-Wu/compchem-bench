# Task: Standardize a Messy SDF (RDKit)

## Background

Real-world compound files are messy: molecules arrive as salts, with
counterions, in protonated or deprotonated states, sometimes as zwitterions,
and the same compound often appears more than once in different forms. Before
any downstream modelling, the file must be **standardized**: desalted,
neutralized, deduplicated, and written in a canonical form.

## Your Task

The file `/workspace/assets/messy.sdf` contains 12 molecule records
(salts, charged species, duplicates, and one record RDKit cannot sanitize).
Using RDKit (already installed), standardize it with exactly this recipe:

1. Read the file with `Chem.SDMolSupplier` (default settings). Records that
   RDKit cannot parse/sanitize come back as `None` — **skip** them, but
   count them.
2. **Desalt**: keep only the largest organic fragment of each molecule with
   `rdMolStandardize.LargestFragmentChooser` (default settings).
3. **Neutralize**: remove formal charges with `rdMolStandardize.Uncharger`
   (default settings) — this also neutralizes zwitterions.
4. **Canonicalize + deduplicate**: convert each surviving molecule to its
   canonical **isomeric** SMILES (`Chem.MolToSmiles`, default settings) and
   drop duplicates.
5. Write `standardized.smi` in `/workspace/`: the **sorted** list of unique
   canonical SMILES, one per line.
6. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_input": <int>,
       "n_parsed": <int>,
       "n_failed": <int>,
       "n_unique": <int>
     },
     "units": {
       "n_input": "1",
       "n_parsed": "1",
       "n_failed": "1",
       "n_unique": "1"
     }
   }
   ```

   - `n_input`: total molecule records in the SDF
   - `n_parsed`: records RDKit read successfully
   - `n_failed`: records that came back as `None`
   - `n_unique`: unique standardized molecules (lines in `standardized.smi`)

## Requirements

- Use RDKit's `MolStandardize.rdMolStandardize` machinery — do **not**
  hand-roll string splitting or regex "desalting". The verifier replays the
  exact recipe above with the same RDKit version and compares your output
  set for set, and the counts exactly.
- `standardized.smi` must be sorted lexicographically, one SMILES per line,
  no header.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/messy.sdf`
- Output: `standardized.smi`, `results.json` in `/workspace/`

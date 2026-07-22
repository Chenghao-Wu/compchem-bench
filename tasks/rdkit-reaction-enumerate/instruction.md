# Task: Reaction-Based Library Enumeration (RDKit)

## Background

A standard virtual-library workflow: given a reaction SMARTS and two sets of
building blocks, enumerate all products, remove structures that are
chemically invalid or duplicated, and keep only the ones passing a simple
property filter. Every step must be done with the real cheminformatics
machinery — hand-written "products" are detectably wrong.

## Your Task

- `/workspace/assets/reaction.smirks` — one amide-formation reaction SMARTS
  with two reactant templates (carboxylic acid + primary/secondary amine).
- `/workspace/assets/building_blocks.csv` — columns `role,smiles` with
  `role` ∈ {`acid`, `amine`}.

Using RDKit (already installed), run exactly this pipeline:

1. Build the reaction with
   `rdChemReactions.ReactionFromSmarts(<smarts>)` and call `Initialize()`.
2. Enumerate: for **every** acid × amine pair (in file order), call
   `rxn.RunReactants((acid, amine))` and collect **all** returned products
   (a bifunctional building block legitimately yields more than one).
3. Sanitize each product (`UpdatePropertyCache(strict=False)` then
   `Chem.SanitizeMol`); count and drop any product that fails.
4. Deduplicate by **InChIKey** (`Chem.MolToInchiKey`), keeping first
   occurrence.
5. Filter: keep products with molecular weight (`Descriptors.MolWt`) in the
   **inclusive** range [150.0, 350.0] g/mol **and** at most 8 rotatable
   bonds (`rdMolDescriptors.CalcNumRotatableBonds`).
6. Write `products.smi` in `/workspace/`: the **sorted** list of canonical
   **isomeric** SMILES of the kept products, one per line. Stereochemistry
   carried over from chiral building blocks must be retained.
7. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_pairs": <int>,
       "n_raw_products": <int>,
       "n_failed_sanitize": <int>,
       "n_unique": <int>,
       "n_kept": <int>
     },
     "units": {
       "n_pairs": "1",
       "n_raw_products": "1",
       "n_failed_sanitize": "1",
       "n_unique": "1",
       "n_kept": "1"
     }
   }
   ```

   - `n_pairs`: acid × amine combinations enumerated
   - `n_raw_products`: products returned by `RunReactants` in total
   - `n_failed_sanitize`: products dropped at step 3
   - `n_unique`: products surviving InChIKey dedup
   - `n_kept`: products surviving the property filter (lines in
     `products.smi`)

## Requirements

- Use RDKit's reaction machinery — do **not** assemble products by string
  editing. The verifier **replays the entire pipeline independently** with
  the same RDKit version and compares your kept set exactly
  (order-independent), including stereochemistry, and every count.
- `products.smi` must be sorted lexicographically, one SMILES per line, no
  duplicates.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/reaction.smirks`,
  `/workspace/assets/building_blocks.csv`
- Output: `products.smi`, `results.json` in `/workspace/`

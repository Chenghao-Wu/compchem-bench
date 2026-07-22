# Task: Batch Molecular Descriptor Calculation (RDKit)

## Background

Computing simple molecular descriptors over a list of compounds is the most
common first step of any cheminformatics analysis. Here you will compute five
standard RDKit descriptors for a small compound list and write them to CSV.

## Your Task

The file `/workspace/assets/input_smiles.txt` contains one (not necessarily
canonical) SMILES per line. Using RDKit (already installed):

1. Parse every line with RDKit (`Chem.MolFromSmiles`).
2. For each molecule compute, with the RDKit defaults:
   - **MW** — average molecular weight (`Descriptors.MolWt`)
   - **LogP** — Wildman–Crippen logP (`Crippen.MolLogP`)
   - **TPSA** — topological polar surface area (`rdMolDescriptors.CalcTPSA`)
   - **HBD** — Lipinski H-bond donor count (`Lipinski.NumHDonors`)
   - **HBA** — Lipinski H-bond acceptor count (`Lipinski.NumHAcceptors`)
3. Write `descriptors.csv` in `/workspace/` with **exactly** this header
   row:

   ```
   canonical_smiles,mw,logp,tpsa,hbd,hba
   ```

   followed by one row per input line, **in input order**:
   - `canonical_smiles`: RDKit canonical **isomeric** SMILES
     (`Chem.MolToSmiles`, default settings)
   - `mw`, `logp`, `tpsa`: floating-point values with at least 4 decimal
     places
   - `hbd`, `hba`: integers
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_input": <int>,
       "n_rows": <int>
     },
     "units": {
       "n_input": "1",
       "n_rows": "1"
     }
   }
   ```

   - `n_input`: number of lines in the input file
   - `n_rows`: number of data rows in `descriptors.csv`

## Requirements

- Every input line is a valid molecule; the row count must equal the input
  line count.
- Do **not** hardcode descriptor values. The verifier independently
  recomputes every descriptor for every input line with the same RDKit
  version and compares against your CSV (floats to 1e-4, integers and
  canonical SMILES exactly).
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/input_smiles.txt`
- Output: `descriptors.csv`, `results.json` in `/workspace/`

# Task: Fix a Broken RDKit Analysis Script

## Background

A colleague's script `/workspace/assets/analyze_mols.py` is supposed to read
`/workspace/assets/input.smi` (one SMILES per line), **normalize** every
molecule (standard functional-group representations, e.g. nitro groups),
write the canonical SMILES of every successfully parsed molecule to
`/workspace/mols.smi` (input order), and write count + mean-MW statistics to
`/workspace/results.json`.

The script currently does not run at all, and it contains **three distinct
bugs**:

1. It imports a **removed/deprecated** RDKit standardization API
   (`rdkit.Chem.MolStandardize.standardize.Standardizer` no longer exists —
   the modern API lives in `rdkit.Chem.MolStandardize.rdMolStandardize`).
2. It parses with `sanitize=False` but never calls
   `UpdatePropertyCache`/`SanitizeMol`, so descriptor calculation dies with
   a `getNumImplicitHs() called without preceding call to
   calcImplicitValence()` error.
3. One input line is a genuinely invalid SMILES (impossible valence); the
   script has no handling for unparseable entries and must **skip and
   count** them instead of crashing.

## Your Task

1. Copy the script to `/workspace/analyze_mols.py` and fix **all** bugs so
   it runs cleanly to completion with the installed RDKit version. Keep the
   overall computation intact (normalize each parsed molecule with
   `rdMolStandardize.Cleanup`, canonical isomeric SMILES in input order,
   same outputs) — fix the code, don't replace the task.
2. Run the fixed script so it produces:
   - `/workspace/mols.smi` — one canonical SMILES per **parsed** molecule,
     in input order (unparseable lines skipped)
   - `/workspace/results.json` in the standard CompChemBench schema:

     ```json
     {
       "values": {
         "n_input": <int>,
         "n_parsed": <int>,
         "n_failed": <int>,
         "mw_mean": <float, g/mol>
       },
       "units": {
         "n_input": "1",
         "n_parsed": "1",
         "n_failed": "1",
         "mw_mean": "g/mol"
       }
     }
     ```

## Requirements

- The verifier **re-runs your fixed script itself** (a non-zero exit is a
  hard fail), then independently replays the intended pipeline
  (parse → `Cleanup` → canonical SMILES/MW, skipping unparseable lines)
  and compares against your script's own outputs exactly (SMILES line by
  line, MW to 1e-4). Hardcoding the expected numbers is pointless — your
  script must actually compute them.
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. The broken script and its input are
in `/workspace/assets/`; put your fixed copy at `/workspace/analyze_mols.py`.

# Task: Fix a Broken ASE Analysis Script

## Background

A colleague's analysis script `/workspace/assets/analyze_cu.py` is supposed
to compute, for fcc Cu (lattice constant `a = 3.615` angstrom) with the EMT
potential:

1. the EMT energy per atom, converted to **kJ/mol**, and
2. the nearest-neighbor distance,

and write both to `results.json`. Two problems: the script **crashes** with
an `AttributeError` raised by an outdated API call, and — once it runs —
the energy it reports is **implausible for a metal** (hint: audit the unit
conversion factor; eV → kJ/mol is not the same number as eV → kcal/mol).

## Your Task

1. Copy the script to `/workspace/analyze_cu.py` and fix **all** bugs so it
   runs cleanly with the installed ASE/NumPy versions. Keep the overall
   computation (structure, calculator, and analysis) intact — fix the
   code, don't replace the task.
2. Run the fixed script so it produces `/workspace/results.json` in the
   standard CompChemBench schema:

   ```json
   {
     "values": {
       "energy_kj_mol_per_atom": <float, kJ/mol>,
       "nn_distance": <float, Å>
     },
     "units": {
       "energy_kj_mol_per_atom": "kJ/mol",
       "nn_distance": "Å"
     }
   }
   ```

## Requirements

- The verifier **re-runs your fixed script itself** and independently
  recomputes both quantities with the same ASE/EMT versions; hardcoding
  the expected numbers into the script is pointless — your script's own
  output is what gets checked, against a real recomputation.
- Note that ASE's EMT reports energies relative to its equilibrium-crystal
  reference state, so a small magnitude is expected — but the conversion
  factor must still be the right one.
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. The broken script is in
`/workspace/assets/`; put your fixed copy at `/workspace/analyze_cu.py`.

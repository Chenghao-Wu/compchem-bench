# Task: Equation of State for FCC Copper (ASE/EMT)

## Background

Compute the equation of state (EOS) for face-centered cubic (FCC) copper using
the ASE Effective Medium Theory (EMT) calculator and fit the Birch–Murnaghan
equation of state to obtain equilibrium volume V₀ and bulk modulus B₀.

## Your Task

1. Build an FCC Cu unit cell using `ase.build.bulk('Cu', 'fcc', a=3.6)`.
2. Scale the cell to **7 different volumes**: lattice constants from
   `a = 3.5` Å to `a = 3.7` Å in 7 equal steps (inclusive).
3. For each scaled structure, compute the total energy using the EMT calculator.
4. Fit the Birch–Murnaghan EOS using `ase.eos.EquationOfState`.
5. Write the results:
   - `eos_data.csv`: a CSV file with columns `a_A,V_A3,E_eV` (7 rows,
     one per volume point, no header line)
   - `results.json` in the standard CompChemBench schema:

     ```json
     {
       "values": {
         "V0": <float, Å³>,
         "E0": <float, eV>,
         "B0": <float, GPa>,
         "n_points": <int>
       },
       "units": {
         "V0": "Å³",
         "E0": "eV",
         "B0": "GPa",
         "n_points": "1"
       }
     }
     ```

     (`n_points` = number of EOS data points used, must be 7)

## Requirements

- Use the EMT calculator from `ase.calculators.emt`.
- Perform **7 volume points** (not more, not fewer).
- Do **not** hardcode the fitted values or the E–V data — the verifier
  rebuilds every structure from your CSV and recomputes its EMT energy;
  fabricated data points are rejected.
- Both output files must be valid and non-empty; every key in `values`
  must also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

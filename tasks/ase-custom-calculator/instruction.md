# Task: Implement a Custom ASE Calculator (Morse Potential) and Relax a Cluster

## Background

ASE's `Calculator` interface lets you plug any potential into optimizers,
MD, and NEB. Implement a pair potential from scratch — correctly, forces
included — and use it.

## Your Task

1. Create `/workspace/morse_calculator.py` defining a class
   **`MorseCalculator`** that subclasses `ase.calculators.calculator.Calculator`
   and implements the pair potential

   ```
   V(r) = D_e * ( (1 - exp(-a * (r - r_e)))^2 - 1 )
   ```

   summed over all unique atom pairs (no cutoff, cluster is non-periodic),
   with parameters **D_e = 0.5 eV, a = 1.5 Å⁻¹, r_e = 2.5 Å** (hardcode
   them; the constructor must work with no arguments).

   - `implemented_properties` must include `"energy"` and `"forces"`.
   - `calculate()` must fill `self.results["energy"]` (float, eV) and
     `self.results["forces"]` (array, eV/Å) with the **analytic** gradient.
2. Load the starting cluster `/workspace/assets/start.xyz` (5 Cu atoms),
   attach your calculator, and relax it (e.g. `ase.optimize.BFGS`) until
   the maximum force is below **0.05 eV/Å**.
3. Write the relaxed structure to `relaxed.xyz`.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, eV>,
       "max_force": <float, eV/Å>,
       "n_steps": <int>
     },
     "units": {
       "final_energy": "eV",
       "max_force": "eV/Å",
       "n_steps": "1"
     }
   }
   ```

   - `final_energy`: energy of the relaxed structure under YOUR calculator
   - `max_force`: maximum force magnitude after relaxation
   - `n_steps`: number of optimizer steps taken

## Requirements

- The verifier **imports your `MorseCalculator`** and evaluates it on
  hidden geometries, comparing energy and forces against its own analytic
  implementation of the same potential — including a finite-difference
  force check. A calculator whose forces are inconsistent with its energy
  (a classic chain-rule slip) fails even if every reported number looks
  right.
- The relaxed structure is checked with the verifier's own implementation:
  it must be a true force minimum of THIS potential.
- `results.json` must follow the schema above: every key in `values` must
  also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

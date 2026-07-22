# Task: Geometry Optimization of a Water Molecule (ASE)

## Background

Use the Atomic Simulation Environment (ASE) to perform a geometry
optimization of a water molecule. The calculator is **fixed** for this task
(see below) so that results are reproducible and independently checkable.

## Your Task

1. Create a water molecule (H2O) with a reasonable starting geometry.
2. Attach **exactly** this calculator to the atoms:

   ```python
   from ase.calculators.lj import LennardJones
   mol.calc = LennardJones(epsilon=0.01, sigma=1.0, rc=5.0)
   ```

   (a generic Lennard-Jones pair potential; the task is about running the
   optimization workflow correctly, not about physical accuracy for water).
3. Run a geometry optimization (e.g. `ase.optimize.BFGS`) until the maximum
   force on any atom is below **0.05 eV/Å**.
4. Write the full optimization trajectory (all frames, including the initial
   structure) to `opt.traj` in your current working directory.
5. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "final_energy": <float, eV>,
       "max_force": <float, eV/Å>,
       "n_steps": <int>,
       "oh_bond_length": <float, Å>
     },
     "units": {
       "final_energy": "eV",
       "max_force": "eV/Å",
       "n_steps": "1",
       "oh_bond_length": "Å"
     }
   }
   ```

   - `final_energy`: total energy of the optimized structure with the
     calculator above
   - `max_force`: maximum force magnitude after optimization
   - `n_steps`: number of optimization steps taken
   - `oh_bond_length`: the O–H bond length of the first O–H pair in the
     optimized structure

## Requirements

- Use ASE (version already installed in your environment) with **exactly**
  the calculator specified above — no other calculator or parameters.
- Do **not** hardcode the answer — run the actual optimization. The verifier
  independently recomputes the energy and forces of your final structure
  with the same calculator and rejects fabricated trajectories.
- `opt.traj` must be a valid ASE trajectory readable by `ase.io.read` and
  contain at least two frames (initial + optimized).
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

Your working directory is `/workspace`. Write all output there.

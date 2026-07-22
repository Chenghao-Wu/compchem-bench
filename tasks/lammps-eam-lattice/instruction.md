# Task: Equilibrium Lattice Constant and Cohesive Energy of Cu (LAMMPS/EAM)

## Background

The equilibrium lattice constant and cohesive energy of a metal are basic
properties delivered by an interatomic potential. Given an EAM potential for
Cu, find them by energy minimization.

## Your Task

`/workspace/assets/Cu_mishin1.eam.alloy` is a Mishin EAM potential for Cu
(`pair_style eam/alloy`, `units metal`).

1. Build a 4×4×4 FCC Cu supercell (256 atoms) at an initial lattice
   constant of **3.7 Å** (deliberately off equilibrium).
2. Run an energy minimization **with box relaxation** (e.g.
   `fix box/relax iso 0.0`) so the cell can relax to equilibrium.
3. Keep `log.lammps` in `/workspace/` and write the final structure with
   `write_data final.data` (in `/workspace/`).
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "a0": <float>,
       "ecoh": <float>
     },
     "units": {
       "a0": "Å",
       "ecoh": "eV/atom"
     }
   }
   ```

   - `a0`: converged lattice constant (box length divided by 4)
   - `ecoh`: cohesive energy = potential energy per atom of the relaxed
     structure (negative)

## Requirements

- Parse the **actual** minimization output — do not hardcode textbook
  values. The verifier checks the log for the LAMMPS banner, minimization
  stats, and completion footer; requires `results.json` to agree with the
  log's final thermo line and with `final.data`; and **independently
  re-evaluates** the energy of `final.data` with the same potential
  (`run 0`), requiring it to match the log. The only way through is a
  genuine minimization.
- Do not modify `/workspace/assets/` — the potential is pinned by sha256.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/Cu_mishin1.eam.alloy`
- Output: `log.lammps`, `final.data`, `results.json` in `/workspace/`

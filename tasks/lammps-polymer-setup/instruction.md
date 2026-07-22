# Task: Build and Equilibrate a Bead-Spring Polymer Melt (LAMMPS)

## Background

Setting up a polymer melt from scratch — generating an initial topology,
writing a valid LAMMPS data file, and getting a clean MD run out of it — is
the canonical LAMMPS workflow task. No prepared inputs are provided: you
build everything.

## Your Task

Build a **Kremer–Grest bead-spring polymer melt** and equilibrate it:

- **System**: 10 chains × 20 beads = 200 monomers, one atom type, one bond
  type, all masses 1.0 (LJ reduced units)
- **Density**: 0.85 σ⁻³ → cubic box of side L = (200/0.85)^(1/3) ≈ 6.1794,
  origin at (0, 0, 0)
- **Bonds**: FENE, `bond_style fene`, `bond_coeff 1 30.0 1.5 1.0 1.0`,
  with `special_bonds fene`
- **Pairs**: WCA, `pair_style lj/cut 1.12246204830937`,
  `pair_coeff * * 1.0 1.0 1.12246204830937`, `pair_modify shift yes`
- **Data file**: `atom_style molecular` (Atoms lines: `id mol type x y z`),
  consecutive beads of a chain bonded (9 bonds per chain, 190 total)

Workflow:

1. Write a builder (Python or any tool) that generates a non-overlapping
   initial configuration (e.g. self-avoiding random walks) and writes
   `polymer.data` to `/workspace/`.
2. Run an NVT equilibration: `velocity all create 1.0 8675309`,
   `timestep 0.006`, `fix ... all nvt temp 1.0 1.0 1.0`,
   `thermo 100` with `thermo_style custom step temp pe`, **3000 steps**.
   Keep `log.lammps` in `/workspace/`.
3. Write the final state with `write_data final.data` (in `/workspace/`).
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_atoms": <int>,
       "n_bonds": <int>,
       "density": <float>,
       "final_pe": <float>
     },
     "units": {
       "n_atoms": "1",
       "n_bonds": "1",
       "density": "σ^-3",
       "final_pe": "ε/atom"
     }
   }
   ```

## Requirements

- The run must be real and the files must tell one story. The verifier
  checks the topology of `polymer.data` (atom/bond counts, per-atom bond
  degree, connected chains), the density, the log structure — and then
  **re-evaluates both data files with LAMMPS** (`read_data` + `run 0`
  using the exact force field above): the initial configuration's energy
  must match the log's first thermo line, and `final.data`'s energy must
  match the log's last thermo line. It also verifies the system actually
  evolved (initial vs final configurations must differ). A hand-fabricated
  data file cannot pass these re-evaluations.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: none (build from the specification above)
- Output: `polymer.data`, `log.lammps`, `final.data`, `results.json` in
  `/workspace/`

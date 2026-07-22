# shared/potentials

Cross-task potential / pseudopotential / basis-set assets, copied into task
images as needed. Every file here must be **freely redistributable** (see the
repository README §Commercial-Software Policy) and carry a license note.

## Layout

- `eam/` — EAM/alloy force-field files for LAMMPS tasks (e.g. Cu EAM used by
  `lammps-eam-lattice`).
- `gth/` — GTH pseudopotentials + MOLOPT basis sets for CP2K tasks (as
  shipped with CP2K).
- `qe/` — Quantum ESPRESSO pseudopotentials from the open PSlibrary 1.0.0
  PBE set (Si, C, O), with provenance and hashes in `qe/SOURCES.md`. Plane-wave
  tasks copy the files they consume into `environment/assets/` and hash them
  like any other asset (see README §Conventions → Asset integrity).

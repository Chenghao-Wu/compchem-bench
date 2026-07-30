# CompChemBench — Dataset Card

> **Status note:** all counts, task lists, and pinned versions below reflect
> the current 42-task repository state.

## 1. Overview and Motivation

CompChemBench is a benchmark for evaluating AI agents on **computational
chemistry** work: preparing inputs, running simulations, parsing and analyzing
outputs, debugging broken setups, and chaining multi-step workflows — across
the tools working computational chemists actually use.

The dataset follows the **Terminal-Bench / Harbor (TB 2.0) task format**, so
any harness that speaks that format can run it out of the box. Two design
decisions differentiate it from static QA-style benchmarks:

1. **Real execution.** Tasks run inside Docker images with the real software
   stack available (LAMMPS, CP2K, Quantum ESPRESSO, xtb, ASE, RDKit). An
   explicit online-bootstrap task may require the agent to install its
   declared runtime stack first. The
   oracle solution (`solution/solve.sh`) performs the actual calculation — no
   hardcoded answers — and agents are expected to do the same.
2. **Anti-cheat evaluation with real cross-verification.** Scoring is not
   string matching against expected files. A four-layer verifier culminates in
   an *independent recompute* (layer 4): the verifier uses the in-image
   software to re-evaluate the agent's final state and requires the agent's
   native log, reported results, and the recomputed value to agree. The only
   way through is to have actually run the calculation.

## 2. Coverage

### Software × category matrix

| Software \ Category | input-prep | execution | analysis | debugging | workflow | Total |
|---|---|---|---|---|---|---|
| ASE | 2 | 2 | 2 | 1 | 3 | **10** |
| LAMMPS | 1 | 2 | 3 | 2 | 1 | **9** |
| CP2K | — | 4 | 1 | 1 | — | **6** |
| QE | 1 | 2 | 2 | 1 | 1 | **7** |
| RDKit | 2 | 1 | 2 | 1 | 1 | **7** |
| xtb | — | 2 | 1 | — | — | **3** |
| **Total** | **6** | **13** | **11** | **6** | **6** | **42** |

### Difficulty distribution

| Difficulty | Count | Share |
|---|---|---|
| easy | 10 | 23.8% |
| medium | 18 | 42.9% |
| hard | 14 | 33.3% |

### Complete task list

**ASE (10)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `ase-geoopt-h2o` | easy | execution | Geometry-optimize a water molecule (ASE/LJ). |
| `ase-eos-cu` | medium | analysis | Fit the equation of state of fcc Cu (EMT). |
| `ase-structure-build` | easy | input-prep | Build an fcc Cu supercell. |
| `ase-format-convert` | medium | input-prep | Convert a CIF to extxyz and LAMMPS data formats. |
| `ase-script-debug` | medium | debugging | Fix a broken ASE analysis script. |
| `ase-neb-adatom` | medium | execution | NEB barrier for an adatom hop on Cu(100) (EMT). |
| `ase-vibrations` | hard | analysis | Finite-displacement vibrational analysis of a Cu4 cluster. |
| `ase-custom-calculator` | hard | workflow | Implement a custom Morse-potential ASE calculator and relax a cluster. |
| `ase-mlip-multihead-offline` | hard | workflow | Run preinstalled DPA-3.2-5M and MatterSim checkpoints on molecular and surface structures. |
| `ase-mlip-multihead-online` | hard | workflow | Bootstrap the MLIP packages and checkpoints online, then run the same four CPU calculations. |

**LAMMPS (9)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `lammps-lj-melt` | easy | execution | Run a Lennard-Jones melt simulation. |
| `lammps-nvt-rdf` | medium | analysis | NVT MD and radial distribution function. |
| `lammps-input-fix` | easy | debugging | Fix a broken LAMMPS input script. |
| `lammps-data-build` | medium | input-prep | Build a LAMMPS data file for bulk Cu. |
| `lammps-eam-lattice` | medium | analysis | Equilibrium lattice constant and cohesive energy of Cu (EAM). |
| `lammps-restart-continue` | medium | execution | Continue a simulation from a restart file. |
| `lammps-msd-diffusion` | hard | analysis | Self-diffusion coefficient from mean-squared displacement. |
| `lammps-thermostat-audit` | hard | debugging | Audit a thermostat setup for correctness. |
| `lammps-polymer-setup` | hard | workflow | Build and equilibrate a bead-spring polymer melt. |

**CP2K (6)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `cp2k-h2o-sp` | easy | execution | DFT single-point energy of water. |
| `cp2k-geoopt-nh3` | medium | execution | DFT geometry optimization of ammonia. |
| `cp2k-input-debug` | easy | debugging | Fix a broken CP2K input file. |
| `cp2k-cell-opt-nacl` | medium | execution | DFT cell optimization of rocksalt NaCl. |
| `cp2k-aimd-water` | hard | execution | Ab initio MD of a single water molecule (NVE). |
| `cp2k-basis-convergence` | hard | analysis | Basis-set convergence of the methanol energy. |

**Quantum ESPRESSO (7)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `qe-scf-si` | easy | execution | Plane-wave DFT SCF of crystalline silicon. |
| `qe-relax-co` | medium | execution | Plane-wave DFT geometry relaxation of carbon monoxide. |
| `qe-output-parse` | medium | analysis | Parse a real `pw.x` output file. |
| `qe-input-relax` | medium | input-prep | Write a `vc-relax` input for zinc-blende SiC. |
| `qe-ecutwfc-convergence` | medium | analysis | Plane-wave cutoff convergence for silicon. |
| `qe-bands-si` | hard | workflow | Band structure of silicon: scf → bands → `bands.x`. |
| `qe-error-diagnose` | hard | debugging | Diagnose and fix three failing `pw.x` runs. |

**RDKit (7)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `rdkit-smiles-canonicalize` | easy | input-prep | Canonicalize SMILES. |
| `rdkit-conformer-mmff` | medium | execution | Conformer generation and MMFF optimization. |
| `rdkit-descriptors-batch` | easy | analysis | Batch molecular descriptor calculation. |
| `rdkit-mol-standardize` | medium | input-prep | Standardize a messy SDF. |
| `rdkit-script-debug` | medium | debugging | Fix a broken RDKit analysis script. |
| `rdkit-reaction-enumerate` | hard | workflow | Reaction-based library enumeration. |
| `rdkit-conformer-cluster` | hard | analysis | Conformer ensemble generation and Butina clustering. |

**xtb (3)**

| Task | Difficulty | Category | Summary |
|---|---|---|---|
| `xtb-singlepoint-gfn2` | easy | execution | GFN2-xTB single-point energy of acetonitrile. |
| `xtb-geoopt-caffeine` | medium | execution | GFN2-xTB geometry optimization of caffeine. |
| `xtb-freq-thermo` | hard | analysis | GFN2-xTB vibrational frequencies and thermochemistry of ethanol. |

The roster above is generated to agree with `registry.toml` (name, difficulty,
category); lint enforces that agreement mechanically.

## 3. Anti-Cheat Design

Scoring is terminal-state verification hardened in four layers, plus a static
asset-integrity layer and CI baselines that every task must pass before merge.

- **Layer 0 — asset integrity.** `/workspace/assets` is agent-writable, so the
  verifier never trusts the workspace copy of any asset it consumes. Every
  asset read by `verify.py` is pinned by sha256 in `tests/refs.json` under
  `"asset_hashes"` and validated before use; a mismatch is a hard fail.
  Enforced statically by lint.
- **Layer 1 — existence.** Required output files must exist.
- **Layer 2 — native output integrity.** The software's *native* output (log,
  restart, XML, …) must be present, complete, and internally consistent —
  e.g. a QE `pw.x` stdout energy must agree with the XML `<etot>` to a tight
  tolerance. Stub or hand-written files fail here.
- **Layer 3 — numerical tolerance.** Reported values (uniform `results.json`
  schema: `values` + `units`) must match calibrated references within
  calibrated tolerances.
- **Layer 4 — real cross-verification.** Medium+ execution/analysis tasks
  independently recompute with the in-image software (ASE calculator, CP2K
  binary, LAMMPS, `pw.x`, …) from the agent's final state and require the
  native log, `results.json`, and the recomputed value to agree. Missing or
  abnormal intermediate structures are a hard fail, never a warning or skip.

**Informed-cheat baseline.** Every task ships a cheat script that produces a
*plausible, self-consistent, domain-aware* forgery of all required files — not
`echo`/`touch` stubs — and CI requires it to fail.

**CI gates** (`.ci/run_ci.sh`, per task):

1. structural lint;
2. image build;
3. **oracle** — `solution/solve.sh` must pass `tests/test.sh` 3/3 runs;
4. **null agent** — empty workspace must fail;
5. **cheat agent** — the informed forgery must fail.

**Lint calibration gates** (`.ci/lint_task.py`): required files; fixed tag
vocabulary (software → method → category → qualifiers); `task.toml` ↔
`registry.toml` consistency; Dockerfile must not COPY `tests/` or `solution/`
(including via `COPY --from`); `instruction.md` must not leak reference values
(any refs.json key or value appearing in the instruction is a lint failure);
`results.json` values/units schema documentation; asset-hash pinning.

## 4. How to Run

### With Harbor

Tasks follow the Harbor / TB 2.0 layout, so they can be run by any harness
that consumes that format — point your Harbor runner at the `tasks/`
directory (or a single `tasks/<task-name>/`) and select your agent. Each task
is self-contained: the harness builds `environment/Dockerfile`, gives the
agent `instruction.md` inside the container, then runs `tests/test.sh` after
the agent finishes (or its timeout expires). Networking is disabled by
default. A task tagged `online-bootstrap` may enable it during the agent
phase; the CI runner disconnects networking before verification.

### Compute budget

Budgets are sized so the agent's *skill*, not its wall-clock speed, is the
binding constraint (calibrated against the first agent baseline; see
`baselines/`):

- **Heavy-software tasks (CP2K, Quantum ESPRESSO)** run with `cpus = 2` and
  agent timeouts of 1200–3600 s (2–3× the pre-baseline values). The CP2K
  images additionally pin `OMP_NUM_THREADS=2` in the Dockerfile: the
  `cp2k:…_psmp` build otherwise spawns one OpenMP thread per *host* core —
  the cgroup CPU quota is invisible to it — and oversubscription thrashes a
  2-CPU container to ~1 effective core. QE images likewise pin
  `OMP_NUM_THREADS=2`. With pinning, e.g. the full 20-step
  `cp2k-aimd-water` trajectory takes ~45 s at 2 CPUs.
- **CPU MLIP workflow tasks** run with `cpus = 4`, `memory_gb = 16`, and
  1800–3600 s agent timeouts. The online variant receives the longer timeout
  for dependency and checkpoint acquisition.
- **Easy tasks** across all software use a uniform 900 s agent timeout
  (pre-baseline: 300–600 s), comfortably above the slowest observed
  first-round easy run (~175 s) so slow-reasoning models are not
  speed-gated.
- All reference values and numerical tolerances are unaffected by these
  budget settings; budgets were validated by re-running the full CI gate
  (oracle 3/3, null, cheat) on every changed task.

### Task directory format

```
tasks/<software>-<topic>-<qualifier>/
├── task.toml             # metadata / verifier / agent / environment config
├── instruction.md        # shown to the agent; contains no reference values
├── environment/
│   ├── Dockerfile        # pinned versions; never COPYs tests/ or solution/
│   └── assets/           # input files, pre-generated outputs, structures
├── solution/
│   └── solve.sh          # oracle: real execution, no hardcoded answers
└── tests/
    ├── test.sh           # entrypoint: runs verify.py, writes reward.txt
    ├── verify.py         # four-layer terminal-state verification
    └── refs.json         # reference values + tolerances + hashes (never in image)
```

### `reward.txt` semantics

`tests/test.sh` runs `verify.py` and writes `/logs/verifier/reward.txt`:
**`1` = pass, `0` = fail.** Rewards are binary; there is no partial credit.
The full verifier log is kept alongside at `/logs/verifier/verify.log`.

### Local CI (requires Docker)

```bash
python3 .ci/lint_task.py tasks/ase-geoopt-h2o   # lint one task
.ci/run_ci.sh tasks/ase-geoopt-h2o              # full 5-step CI for one task
```

## 5. Reproducibility

- **Canonical architecture: x86_64.** All calibration is performed on x86_64
  and each `refs.json` records its `arch`. Other architectures may produce
  different floating-point tails and are not the calibration target.
- **Pinned images.** Every image pins exact versions (tag + digest where the
  base is a registry image; exact build/tarball hashes otherwise):

| Software | Pin | Tasks |
|---|---|---|
| Quantum ESPRESSO | **7.4** (conda-forge build `hac89879_0`) | 7 |
| xtb | **6.7.1** (official static linux-x86_64 tarball, sha256-verified) | 3 |
| CP2K | **2024.1** (`cp2k/cp2k:2024.1_mpich_generic_psmp`) | 6 |
| LAMMPS | **patch_7Jan2022** (`lammps/lammps:patch_7Jan2022_ubuntu20.04_openmpi_py3`) | 9 |
| RDKit | **2024.9.5** (pip, on `python:3.11.9-slim`) | 7 |
| ASE | **3.23.0** for existing tasks; MLIP workflows use **3.26.0** with CPU PyTorch 2.10.0 | 10 |

- **Network isolation by default.** Standard tasks use `network=false` and
  bake every dependency into the image. Explicit `online-bootstrap` tasks
  receive network access only while the agent prepares the environment; the
  verifier runs after that network is disconnected.
- **Determinism.** Fixed seeds; single-threaded or fixed-rank MPI (e.g. QE runs
  calibrate at 1 MPI rank × 2 OMP threads).
- **Calibration protocol.** The oracle is run **≥ 5 times** on the CI image;
  tolerance = **max(3 × observed spread, physical minimum resolution)**.
  Deterministic tasks (zero observed spread) use the physical minimum
  resolution. Each `tests/refs.json` records the calibrated values and
  tolerances together with the **image digest, calibration date, and arch**,
  plus a `_calibration_note` describing the protocol outcome.

## 6. License and Commercial-Software Policy

CompChemBench itself is released under the **Apache License 2.0** (see
`LICENSE`; copyright 2026 Chenghao Wu).

CompChemBench **excludes commercial software by design** — no VASP (removed per
project decision), no Gaussian, no licensed tier, no `requires-license` tag.
Every task must run *and recompute* end-to-end on freely redistributable
tools, which is what makes the layer-4 cross-verification possible for every
task. Plane-wave DFT execution is covered by Quantum ESPRESSO,
cheminformatics by RDKit, and cheap semi-empirical execution by xtb.

All bundled software is open source. Pseudopotentials are from the open
**PSlibrary 1.0.0 PBE** set (Si, C, O — redistributable; provenance and
sha256 hashes in `shared/potentials/qe/SOURCES.md`); CP2K tasks use the GTH
pseudopotentials and MOLOPT basis sets shipped with CP2K; LAMMPS tasks use
open EAM/force-field files (see `shared/potentials/README.md`).

## 7. Data Contamination Policy and Held-Out Plan

**Please do not train on this dataset.** This public repository contains the
reference answers (`tests/refs.json`) and oracle solutions (`solution/`) —
that is what makes it a usable evaluation benchmark, and also what makes it
contaminating as training data. In the spirit of the Terminal-Bench
anti-contamination policy, we ask that CompChemBench (tasks, instructions,
reference values, and solutions) be excluded from training corpora; models
trained on it can no longer be meaningfully evaluated by it.

- **No reference values in agent-visible text.** `instruction.md` never
  contains reference values (lint-enforced), and `tests/refs.json` never
  enters the image, so the calibration targets are not present in any
  agent-reachable artifact.
- **Oracle solutions are not agent-visible.** `solution/` is never copied
  into the image (lint-enforced, including multi-stage `COPY --from`
  smuggling).
- **Parameterized instances.** Tasks are designed around parameterized
  generators (structures, compositions, cutoffs, seeds), so fresh instances
  can be produced without redesigning the task.
- **Held-out plan.** A held-out split will be generated from these
  parameterized families — new instances with fresh parameters and
  re-calibrated references, kept out of the public repo — to probe
  contamination and overfitting against the public 42.

## 8. Repository Layout

```
compchem-bench/
├── README.md
├── DATASET_CARD.md               # this file
├── registry.toml                 # dataset index (name, tags, difficulty)
├── shared/                       # cross-task assets (copied into images as needed)
│   ├── potentials/               #   EAM/force-field files, GTH pseudopotentials, basis sets
│   └── structures/               #   common CIF/xyz starting structures
├── tasks/                        # 40 task directories (see §2)
└── .ci/
    ├── run_ci.sh                 # local CI runner (requires Docker)
    └── lint_task.py              # structural lint checks
```

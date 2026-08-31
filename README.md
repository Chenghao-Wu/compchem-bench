

# CompChemBench

A benchmark for evaluating AI agents on **real computational chemistry work** —
preparing inputs, running simulations, parsing outputs, debugging broken
setups, and chaining multi-step workflows — across the open-source tools
working computational chemists actually use: **ASE, LAMMPS, CP2K, Quantum
ESPRESSO, RDKit, and xtb**.

Tasks follow the **Terminal-Bench / Harbor (TB 2.0) task format**, so any
harness that speaks that format can run the benchmark out of the box. Scoring
is terminal-state verification hardened by an *independent recompute*: the
verifier re-evaluates the agent's final state with the in-image software, so
the only way to pass is to have actually run the calculation.

See **[DATASET_CARD.md](DATASET_CARD.md)** for the full dataset card —
complete task list, anti-cheat design, pinned-image inventory, calibration
protocol, and contamination policy — and **[baselines/](baselines/README.md)**
for the current leaderboard.

> **Note for model developers and trainers:** this repository contains task
> reference answers and oracle solutions (it is an evaluation benchmark).
> **Please do not train on it.** See [Data contamination policy](#data-contamination-policy)
> below.

## Coverage (v1.1 — 46 tasks)

Tasks are organized by **capability** — the cognitive skill being measured —
with software as a secondary tag.

| Capability \ Difficulty | easy | medium | hard | Total |
|---|---|---|---|---|
| system-construction | 2 | 5 | 2 | **9** |
| adaptive-convergence | — | 1 | 1 | **2** |
| property-estimation | 6 | 10 | 8 | **24** |
| scientific-auditing | — | — | 5 | **5** |
| failure-recovery | 2 | 2 | 2 | **6** |
| cross-code-orchestration | — | — | — | **0** |
| **Total** | **10** | **18** | **18** | **46** |

Difficulty distribution: **10 easy / 18 medium / 18 hard** (22% / 39% / 39%).
The full per-task list, capability definitions, and the software × capability
cross-tab are in [DATASET_CARD.md §2](DATASET_CARD.md#2-coverage).

## Quick start

Tasks are self-contained Harbor/TB 2.0 directories. Point your Harbor runner
at `tasks/` (or a single `tasks/<task-name>/`) and select your agent — the
harness builds `environment/Dockerfile`, gives the agent `instruction.md`
inside the container (with `network=false`), then runs `tests/test.sh`, which
writes `/logs/verifier/reward.txt`: **`1` = pass, `0` = fail** (binary, no
partial credit).

Local CI (requires Docker):

```bash
python3 .ci/lint_task.py tasks/ase-geoopt-h2o   # structural lint for one task
.ci/run_ci.sh tasks/ase-geoopt-h2o              # full 5-step CI gate for one task
.ci/run_all.sh                                  # re-run the CI gate over all 46 tasks
```

## Repository layout

```
compchem-bench/
├── README.md
├── DATASET_CARD.md               # dataset card (task list, anti-cheat, reproducibility)
├── registry.toml                 # dataset index (name, software, capability, difficulty, tags)
├── baselines/                    # leaderboard + baseline run reports (JSON + Markdown)
├── shared/                       # cross-task assets (copied into images as needed)
│   ├── potentials/               #   EAM/force-field files, GTH pseudopotentials, basis sets
│   └── structures/               #   common CIF/xyz starting structures
├── tasks/
│   └── <software>-<topic>-<qualifier>/
│       ├── task.toml             # metadata / verifier / agent / environment config
│       ├── instruction.md        # task description shown to agent (no reference values)
│       ├── environment/
│       │   ├── Dockerfile        # pinned versions; never COPYs tests/ or solution/
│       │   └── assets/           # input files, pre-generated outputs, structures
│       ├── solution/
│       │   └── solve.sh          # oracle: real execution, no hardcoded answers
│       └── tests/
│           ├── test.sh           # entrypoint: calls verify.py, writes reward.txt
│           ├── verify.py         # terminal-state verification logic
│           └── refs.json         # reference values + tolerances (never enters image)
└── .ci/
    ├── run_ci.sh                 # local CI runner (requires Docker)
    ├── run_all.sh                # full-suite CI driver
    └── lint_task.py              # structural lint checks
```

## Anti-cheat design (summary)

Scoring is terminal-state verification in four layers, plus a static
asset-integrity layer — details in [DATASET_CARD.md §3](DATASET_CARD.md#3-anti-cheat-design):

- **Asset integrity.** `/workspace/assets` is agent-writable, so every asset
  the verifier consumes is pinned by sha256 in `tests/refs.json` and validated
  before use; a mismatch is a hard fail. Enforced statically by lint.
- **Existence → native-output integrity → numerical tolerance →
  cross-verification.** The final layer recomputes from the agent's final
  state with the in-image software (ASE calculator, CP2K binary, LAMMPS,
  `pw.x`, …) and requires the native log, the reported `results.json`, and the
  recomputed value to agree within a tight tolerance.
- **Informed-cheat baseline.** Every task ships a cheat script producing a
  plausible, self-consistent forgery of all required files, and CI requires it
  to fail — alongside the oracle (must pass 3/3) and null-agent (must fail)
  gates.

## Reproducibility (summary)

- Canonical architecture **x86_64**; every image pins exact versions (tag +
  digest / tarball hash) — inventory in [DATASET_CARD.md §5](DATASET_CARD.md#5-reproducibility).
- **Hermetic runtime**: `network=false` at run time; all dependencies are in
  the image.
- **Calibration protocol**: the oracle is run ≥ 5 times on the CI image;
  tolerance = max(3 × observed spread, physical minimum resolution); calibrated
  values, tolerances, image digest, calibration date, and arch are recorded in
  each `tests/refs.json`.

## Baselines

Current official leaderboard entry (see [baselines/README.md](baselines/README.md)
for the full table and how to submit a new result):

| Model | Agent | Date | Pass rate |
|---|---|---|---|
| `deepseek-v4-pro` (DeepSeek API) | Claude Code 2.1.215 | 2026-07-21 | **32/40 = 80.0%** |

## Data contamination policy

This is an **evaluation benchmark**, and this public repository contains the
reference answers (`tests/refs.json`) and oracle solutions
(`solution/solve.sh`). In the spirit of the Terminal-Bench anti-contamination
policy:

- **Do not include this dataset — tasks, instructions, reference values, or
  solutions — in training corpora.** Models trained on it can no longer be
  meaningfully evaluated by it.
- Agent-visible artifacts are kept clean by construction: `instruction.md`
  never contains reference values (lint-enforced) and neither `tests/` nor
  `solution/` enters the runtime image.
- A **held-out private split** (fresh parameterized instances with
  re-calibrated references, kept out of this repository) is the planned
  follow-up for probing contamination and overfitting against the public 46
  tasks. See [DATASET_CARD.md §7](DATASET_CARD.md#7-data-contamination-policy-and-held-out-plan).

## Commercial-software policy

CompChemBench **excludes commercial software by design** (no VASP, no
Gaussian): every task must run *and recompute* end-to-end on freely
redistributable tools. Plane-wave DFT execution is covered by Quantum
ESPRESSO, cheminformatics by RDKit, and cheap semi-empirical execution by xtb.
There is no licensed tier and no `requires-license` tag.

## License

CompChemBench is released under the **Apache License 2.0** — see
[LICENSE](LICENSE). Copyright 2026 Chenghao Wu. Bundled third-party software,
pseudopotentials, and force fields remain under their own (open) licenses;
provenance and redistribution status are documented in
[DATASET_CARD.md §6](DATASET_CARD.md#6-license-and-commercial-software-policy)
and `shared/potentials/`.

## Contributing

Issues and pull requests are welcome — especially new tasks in uncovered
capability × software cells, and new baseline results (see
[baselines/README.md](baselines/README.md) for the submission format). New
tasks must pass the full CI gate (lint, oracle 3/3, null-agent fail,
informed-cheat fail) described in
[DATASET_CARD.md §3](DATASET_CARD.md#3-anti-cheat-design).

## Citation

If you use CompChemBench in your work, please cite this repository
(citation metadata will be added with the public release):

```bibtex
@misc{compchembench2026,
  title  = {CompChemBench: A Benchmark for AI Agents on Computational Chemistry Tasks},
  author = {Wu, Chenghao},
  year   = {2026},
  url    = {https://github.com/Chenghao-Wu/compchem-bench}
}
```

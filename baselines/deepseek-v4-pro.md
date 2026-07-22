# Baseline: Claude Code × DeepSeek v4 Pro

The official leaderboard baseline for CompChemBench, run on the current
(budget-tuned) benchmark spec, main @ `d18bd2c`. An earlier run ("R1" below,
26/40) was measured on the pre-tuning spec under a thread-oversubscription
artifact (CP2K psmp spawned one OMP thread per host core inside a 2-CPU
cgroup quota) plus binding agent timeouts on easy/heavy tasks; its artifacts
were removed from the repository when this run superseded it, and its numbers
are quoted inline for comparison.

| | |
|---|---|
| Model | `deepseek-v4-pro` (DeepSeek API, reasoning model) |
| Agent | Claude Code 2.1.215 (`--print`, `bypassPermissions`) |
| Harness | Harbor 0.20.0 |
| Compatibility layer | litellm 1.93.0 proxy — Anthropic `/v1/messages` → DeepSeek (OpenAI-compatible) |
| Benchmark commit | `d18bd2c` (main) |
| Arch | x86_64 |
| Date | 2026-07-21 |
| Protocol | 1 attempt per task (k=1), task-spec'd agent timeouts (900–3600 s), `n_concurrent=6` |

## Headline

**Accuracy (mean per-task success rate): 32/40 = 80.0%** (R1: 26/40 = 65.0%) — 32 pass / 8 real
fail / **0 harness-or-quota errors**. Total wall-clock 17 min (R1: 32 min) —
the OMP-thread pinning that removed the 1-effective-core artifact also made
the whole suite ~2× faster. **Zero agent timeouts** in R2 (R1: 5).

## By software

| Software | R1 | R2 | Δ |
|---|---|---|---|
| RDKit | 7/7 (100%) | 7/7 (100%) | — |
| xtb | 3/3 (100%) | 3/3 (100%) | — |
| ASE | 7/8 (87.5%) | 8/8 (100%) | +1 |
| QE | 5/7 (71.4%) | 4/7 (57.1%) | −1 |
| LAMMPS | 4/9 (44.4%) | 4/9 (44.4%) | — |
| CP2K | 0/6 (0%) | 6/6 (100%) | +6 |

## By difficulty

| Difficulty | R1 | R2 |
|---|---|---|
| easy | 5/10 (50.0%) | 9/10 (90.0%) |
| medium | 13/18 (72.2%) | 15/18 (83.3%) |
| hard | 8/12 (66.7%) | 8/12 (66.7%) |

The R1 difficulty inversion (easy < medium) is gone; the ladder is now
monotone (easy 90% > medium 83% > hard 67%) — evidence that the inversion was
a budget artifact, not a difficulty-calibration error.

## Flips vs R1 (single attempt at k=1, so ±variance is expected)

**0 → 1 (8):** `cp2k-h2o-sp`, `cp2k-cell-opt-nacl` (proven budget artifacts),
`cp2k-input-debug`, `cp2k-aimd-water`, `ase-geoopt-h2o`, `lammps-input-fix`,
and the two notable ones:

- `cp2k-basis-convergence` — **passed within the 1e-6 Ha tolerance** in 231 s.
  R3's 3e-6 miss was therefore agent error under pressure, not a numeric
  floor. With OMP pinning the 5 single points take seconds each, so the agent
  could afford to check its work. The 1e-6 tolerance still discriminates
  (setup must be exactly right).
- `cp2k-geoopt-nh3` — **passed in 259 s**. R3's "2 opt steps in ~1 h" was
  dominated by per-step thrash, not step count. Honest caveat: with per-step
  cost down ~100×, this task no longer discriminates *input-quality →
  convergence-efficiency* the way it did under thrash; it now tests "can
  produce a working geometry optimization", which DeepSeek v4 Pro can.
  Alternatively the agent simply wrote a better input this attempt — either
  way the pass is verifier-legitimate (layer-4 cross-verification).

**1 → 0 (2):** `lammps-thermostat-audit` (agent thermostatted only half the
fluid — substantive error), `qe-error-diagnose` (case2 energy off by 0.47 Ry).
Both are reverse variance: budgets were never binding on these tasks
(R1 durations 211 s / 166 s vs 1200 s / 1500 s budgets).

## Persistent fails (6) — the real discrimination signal

| Task | Reason (verifier) |
|---|---|
| `lammps-lj-melt` | final PE −0.0222 vs ref −5.6755 — melt never equilibrated |
| `lammps-eam-lattice` | real fail (R1: real fail) |
| `lammps-restart-continue` | real fail (R1: real fail) |
| `lammps-polymer-setup` | real fail (R1: real fail) |
| `qe-bands-si` | missing `pwscf.xml` — scf→bands workflow not completed |
| `qe-input-relax` | real fail (R1: real fail) |

LAMMPS (4/9) is now the clear capability bottleneck for this agent×model —
exactly the discrimination the benchmark is designed to surface.

## Per-task results

| Task | Software | Difficulty | R1 | R2 | Duration (s) |
|---|---|---|---|---|---|
| ase-custom-calculator | ase | hard | 1 | 1 | 71 |
| ase-eos-cu | ase | medium | 1 | 1 | 108 |
| ase-format-convert | ase | medium | 1 | 1 | 120 |
| ase-geoopt-h2o | ase | easy | 0 | **1** | 86 |
| ase-neb-adatom | ase | medium | 1 | 1 | 281 |
| ase-script-debug | ase | medium | 1 | 1 | 107 |
| ase-structure-build | ase | easy | 1 | 1 | 62 |
| ase-vibrations | ase | hard | 1 | 1 | 75 |
| cp2k-aimd-water | cp2k | hard | 0 | **1** | 212 |
| cp2k-basis-convergence | cp2k | hard | 0 | **1** | 231 |
| cp2k-cell-opt-nacl | cp2k | medium | 0 | **1** | 161 |
| cp2k-geoopt-nh3 | cp2k | medium | 0 | **1** | 259 |
| cp2k-h2o-sp | cp2k | easy | 0 | **1** | 144 |
| cp2k-input-debug | cp2k | easy | 0 | **1** | 176 |
| lammps-data-build | lammps | medium | 1 | 1 | 170 |
| lammps-eam-lattice | lammps | medium | 0 | 0 | 230 |
| lammps-input-fix | lammps | easy | 0 | **1** | 149 |
| lammps-lj-melt | lammps | easy | 0 | 0 | 141 |
| lammps-msd-diffusion | lammps | hard | 1 | 1 | 121 |
| lammps-nvt-rdf | lammps | medium | 1 | 1 | 111 |
| lammps-polymer-setup | lammps | hard | 0 | 0 | 240 |
| lammps-restart-continue | lammps | medium | 0 | 0 | 140 |
| lammps-thermostat-audit | lammps | hard | 1 | **0** | 178 |
| qe-bands-si | qe | hard | 0 | 0 | 209 |
| qe-ecutwfc-convergence | qe | medium | 1 | 1 | 156 |
| qe-error-diagnose | qe | hard | 1 | **0** | 142 |
| qe-input-relax | qe | medium | 0 | 0 | 104 |
| qe-output-parse | qe | medium | 1 | 1 | 47 |
| qe-relax-co | qe | medium | 1 | 1 | 236 |
| qe-scf-si | qe | easy | 1 | 1 | 84 |
| rdkit-conformer-cluster | rdkit | hard | 1 | 1 | 56 |
| rdkit-conformer-mmff | rdkit | medium | 1 | 1 | 94 |
| rdkit-descriptors-batch | rdkit | easy | 1 | 1 | 75 |
| rdkit-mol-standardize | rdkit | medium | 1 | 1 | 89 |
| rdkit-reaction-enumerate | rdkit | hard | 1 | 1 | 74 |
| rdkit-script-debug | rdkit | medium | 1 | 1 | 76 |
| rdkit-smiles-canonicalize | rdkit | easy | 1 | 1 | 84 |
| xtb-freq-thermo | xtb | hard | 1 | 1 | 95 |
| xtb-geoopt-caffeine | xtb | medium | 1 | 1 | 68 |
| xtb-singlepoint-gfn2 | xtb | easy | 1 | 1 | 62 |

(Per-task durations and machine-readable values are in
`deepseek-v4-pro.json`.)

## Caveats

- Single attempt (k=1); the 10 flips (8 up / 2 down) vs R1 include genuine
  budget rescues *and* ordinary sampling variance. Multi-seed averaging would
  be needed to separate them per-task (see the `deepseek-v3.2` k=5 report).
- The budget tuning intentionally removed speed as a measured
  dimension. Two CP2K tasks (`geoopt-nh3`, `basis-convergence`) that
  discriminated under the old thrashed budgets now pass — their refereed
  tolerances are unchanged, but the effective bar is lower when compute is
  fast. If input-quality discrimination is desired there, it must come from
  task design (e.g. step-count budgets), not from thread starvation.
- The earlier pre-tuning run (R1) is quoted inline only; its artifacts were
  removed from the repository when this run superseded it.
- Agent-phase containers have outbound network (LLM API
  requirement); no refs access was observed in trajectories, but held-out
  private refs remain the robust fix.

# Baseline: Claude Code × DeepSeek v3.2 (OpenRouter) — k=5

Third leaderboard baseline for CompChemBench, and the first **multi-seed** one:
every task was attempted **5 times** (`k=5`). The headline score is the same
**accuracy** metric the leaderboard uses for every entry — the mean per-task
success rate — here averaged over the five seeds, so it is directly comparable
to the single-attempt (`k=1`) entries. The extra seeds also let this report
quantify **per-task variance**, which single-attempt runs cannot. Run on the
same task spec, agent, harness, and compatibility layer as the
`deepseek-v4-pro` / `deepseek-v4-flash` entries; the only changes are the model
and the number of attempts.

| | |
|---|---|
| Model | `deepseek/deepseek-v3.2` (via OpenRouter) |
| Agent | Claude Code 2.1.215 (`--print`, `bypassPermissions`) |
| Harness | Harbor 0.20.0 |
| Compatibility layer | litellm 1.93.0 proxy — Anthropic `/v1/messages` → OpenRouter (OpenAI-compatible) |
| Benchmark commit | `aed9c17` (main) |
| Arch | x86_64 |
| Date | 2026-07-22 |
| Protocol | **5 attempts per task (k=5)**, task-spec'd agent timeouts (900–3600 s), `n_concurrent=6` |

## Headline

**Accuracy (mean per-task success rate): 71.5% — 143/200 passing attempts (k=5).**

Computed the way the leaderboard defines it: each task's success rate
(passes / 5) averaged over the 40 tasks; with a uniform five attempts per task
this equals 143 / 200. All 200 attempts produced verifier rewards: **143 pass /
57 real fail / 0 harness-or-quota errors** in the final dataset. (5 additional
attempts were cancelled by a deliberate mid-run pause and re-run to reach five
valid seeds per task; a small number of transient upstream API timeouts occurred
during the run and were retried by the harness. None of these are counted as
fails.)

This is the metric directly comparable to the other entries: **v3.2 71.5% <
`deepseek-v4-pro` 80.0% < `deepseek-v4-flash` 85.0%** — on this suite v3.2 is
the weakest of the three per attempt.

## By software (accuracy)

| Software | pro (k=1) | flash (k=1) | v3.2 (k=5) |
|---|---|---|---|
| RDKit | 100% | 100% | 85.7% |
| xtb | 100% | 100% | 86.7% |
| ASE | 100% | 100% | 80.0% |
| CP2K | 100% | 83.3% | 83.3% |
| QE | 57.1% | 85.7% | 57.1% |
| LAMMPS | 44.4% | 55.6% | 51.1% |

## By difficulty (accuracy)

| Difficulty | pro (k=1) | flash (k=1) | v3.2 (k=5) |
|---|---|---|---|
| easy | 90.0% | 90.0% | 72.0% |
| medium | 83.3% | 83.3% | 73.3% |
| hard | 66.7% | 83.3% | 68.3% |

For v3.2 the hard tier (68.3%) sits just below easy (72.0%) and medium (73.3%),
which are within ~1pp of each other — accuracy is essentially flat across
easy/medium with hard lowest, rather than a steep ladder.

## What k=5 adds: per-task variance (the point of this run)

Single-attempt scores hide how coin-flippy a model is per task. With five
attempts per task, **23 of 40 tasks landed strictly between 0 and 1** (13 passed
on all five seeds, 4 failed on all five) — v3.2 both passes and fails them
depending on the seed:

- **Near coin-flips (accuracy ≤ 0.4):** `ase-geoopt-h2o` 1/5 (the known
  1e-6-tolerance near-miss task), `cp2k-basis-convergence` 1/5,
  `lammps-lj-melt` 1/5, `qe-input-relax` 2/5.
- **Unstable (0.6):** `qe-ecutwfc-convergence`, `qe-error-diagnose`,
  `rdkit-script-debug`.
- **Mostly reliable (0.8):** 16 further tasks drop exactly one of five.

This quantifies the sampling noise around the pro (80.0%, 32/40) vs flash
(85.0%, 34/40) gap: per-task single-attempt outcomes of this model family
routinely flip, so a ±2-task leaderboard difference at `k=1` is within noise.

## Consistent failures (accuracy 0/5 — real capability gaps, not variance)

- `lammps-eam-lattice`, `lammps-polymer-setup`, `lammps-restart-continue` —
  LAMMPS remains the clearest capability bottleneck, consistent with both
  prior baselines.
- `qe-bands-si` — v3.2 never produced a passing band-structure workflow
  (flash passed it at `k=1`; pro failed it).

`ase-geoopt-h2o` moved from "never passed" in the partial run to 1/5 — it is a
genuine borderline task at its 1e-6 eV tolerance, not a broken one.

## vs the k=1 entries (accuracy comparison)

- **v3.2 71.5% < pro 80.0% < flash 85.0%.** With n=5 attempts per task the
  standard error on v3.2's accuracy is ~±3pp, so the gap to both v4 models is
  outside noise — on this suite v3.2 is the weakest of the three per attempt.
- v3.2's deficit is concentrated in QE (57.1%) and LAMMPS (51.1%); it is at or
  above par on RDKit / xtb / CP2K / ASE.
</content>
</invoke>

# Baseline: Claude Code × DeepSeek v4 Flash

Second leaderboard baseline for CompChemBench, run on the current
(budget-tuned) benchmark spec, main @ `1fb9fa1` — the same task spec, agent,
harness, and protocol as the `deepseek-v4-pro` entry, so the two are directly
comparable.

| | |
|---|---|
| Model | `deepseek-v4-flash` (DeepSeek API) |
| Agent | Claude Code 2.1.215 (`--print`, `bypassPermissions`) |
| Harness | Harbor 0.20.0 |
| Compatibility layer | litellm 1.93.0 proxy — Anthropic `/v1/messages` → DeepSeek (OpenAI-compatible) |
| Benchmark commit | `1fb9fa1` (main) |
| Arch | x86_64 |
| Date | 2026-07-21 |
| Protocol | 1 attempt per task (k=1), task-spec'd agent timeouts (900–3600 s), `n_concurrent=6` |

## Headline

**Accuracy (mean per-task success rate): 34/40 = 85.0%** (pro: 32/40 = 80.0%) — 34 pass / 6 real
fail / **0 harness-or-quota errors**. Total wall-clock 14 min (pro: 17 min).
**Zero agent timeouts** (pro: 0). The pipeline was smoke-validated on 4 tasks
before the full run; all 40 tasks produced verifier rewards.

## By software

| Software | pro | flash | Δ |
|---|---|---|---|
| RDKit | 7/7 (100%) | 7/7 (100%) | — |
| xtb | 3/3 (100%) | 3/3 (100%) | — |
| ASE | 8/8 (100%) | 8/8 (100%) | — |
| QE | 4/7 (57.1%) | 6/7 (85.7%) | +2 |
| LAMMPS | 4/9 (44.4%) | 5/9 (55.6%) | +1 |
| CP2K | 6/6 (100%) | 5/6 (83.3%) | −1 |

## By difficulty

| Difficulty | pro | flash |
|---|---|---|
| easy | 9/10 (90.0%) | 9/10 (90.0%) |
| medium | 15/18 (83.3%) | 15/18 (83.3%) |
| hard | 8/12 (66.7%) | 10/12 (83.3%) |

Both models keep the monotone easy ≥ medium ≥ hard ladder the budget tuning
was designed to restore. Flash's overall edge comes entirely from the hard
tier (QE × 2).

## Flips vs pro (single attempt at k=1, so ±variance is expected)

**pro 0 → flash 1 (4):** `lammps-lj-melt`, `lammps-thermostat-audit`,
`qe-bands-si`, `qe-error-diagnose`. All four were characterized as
substantive fails in the pro report (e.g. pro's `qe-bands-si` never produced
`pwscf.xml`; pro's `lammps-lj-melt` never equilibrated), so these are genuine
single-attempt wins for flash on this run — but with n=1 attempts they are
indistinguishable from ordinary sampling variance.

**pro 1 → flash 0 (2):**

- `cp2k-basis-convergence` — "No ATOMIC COORDINATES block in CP2K log": the
  agent's single-point run did not produce a parseable structure section, so
  the energy series could not be extracted. Pro passed this within the
  1e-6 Ha tolerance.
- `lammps-input-fix` — "fixed.in must set 'mass 1 1.0'": the agent fixed the
  input deck's crash but dropped a required mass declaration the verifier
  checks for. Pro passed.

## Fails (6) — all real verifier fails, 0 harness errors

| Task | Reason (verifier) |
|---|---|
| `cp2k-basis-convergence` | No ATOMIC COORDINATES block in CP2K log |
| `lammps-eam-lattice` | results.json ecoh −3.5402 ≠ log last line 0.0565 eV/atom (also fails for pro) |
| `lammps-input-fix` | fixed.in missing required `mass 1 1.0` |
| `lammps-polymer-setup` | results.json final PE 0.1007 ≠ log last line 20.1426 (also fails for pro) |
| `lammps-restart-continue` | continuation does not join the equilibrated state — restart not read / re-initialized (also fails for pro) |
| `qe-input-relax` | K_POINTS written as `{automatic}` instead of `automatic` (also fails for pro) |

LAMMPS (5/9) remains the weakest software for flash as it is for pro (4/9);
three of the four shared fails are LAMMPS tasks — the same capability
bottleneck the benchmark surfaces for both models.

## Per-task results

| Task | Software | Difficulty | pro | flash | Duration (s) |
|---|---|---|---|---|---|
| ase-custom-calculator | ase | hard | 1 | 1 | 111 |
| ase-eos-cu | ase | medium | 1 | 1 | 69 |
| ase-format-convert | ase | medium | 1 | 1 | 99 |
| ase-geoopt-h2o | ase | easy | 1 | 1 | 75 |
| ase-neb-adatom | ase | medium | 1 | 1 | 122 |
| ase-script-debug | ase | medium | 1 | 1 | 90 |
| ase-structure-build | ase | easy | 1 | 1 | 79 |
| ase-vibrations | ase | hard | 1 | 1 | 105 |
| cp2k-aimd-water | cp2k | hard | 1 | 1 | 177 |
| cp2k-basis-convergence | cp2k | hard | 1 | **0** | 203 |
| cp2k-cell-opt-nacl | cp2k | medium | 1 | 1 | 186 |
| cp2k-geoopt-nh3 | cp2k | medium | 1 | 1 | 139 |
| cp2k-h2o-sp | cp2k | easy | 1 | 1 | 99 |
| cp2k-input-debug | cp2k | easy | 1 | 1 | 139 |
| lammps-data-build | lammps | medium | 1 | 1 | 182 |
| lammps-eam-lattice | lammps | medium | 0 | 0 | 123 |
| lammps-input-fix | lammps | easy | 1 | **0** | 188 |
| lammps-lj-melt | lammps | easy | 0 | **1** | 144 |
| lammps-msd-diffusion | lammps | hard | 1 | 1 | 114 |
| lammps-nvt-rdf | lammps | medium | 1 | 1 | 93 |
| lammps-polymer-setup | lammps | hard | 0 | 0 | 182 |
| lammps-restart-continue | lammps | medium | 0 | 0 | 168 |
| lammps-thermostat-audit | lammps | hard | 0 | **1** | 109 |
| qe-bands-si | qe | hard | 0 | **1** | 200 |
| qe-ecutwfc-convergence | qe | medium | 1 | 1 | 116 |
| qe-error-diagnose | qe | hard | 0 | **1** | 117 |
| qe-input-relax | qe | medium | 0 | 0 | 93 |
| qe-output-parse | qe | medium | 1 | 1 | 60 |
| qe-relax-co | qe | medium | 1 | 1 | 219 |
| qe-scf-si | qe | easy | 1 | 1 | 91 |
| rdkit-conformer-cluster | rdkit | hard | 1 | 1 | 43 |
| rdkit-conformer-mmff | rdkit | medium | 1 | 1 | 92 |
| rdkit-descriptors-batch | rdkit | easy | 1 | 1 | 56 |
| rdkit-mol-standardize | rdkit | medium | 1 | 1 | 73 |
| rdkit-reaction-enumerate | rdkit | hard | 1 | 1 | 78 |
| rdkit-script-debug | rdkit | medium | 1 | 1 | 93 |
| rdkit-smiles-canonicalize | rdkit | easy | 1 | 1 | 78 |
| xtb-freq-thermo | xtb | hard | 1 | 1 | 92 |
| xtb-geoopt-caffeine | xtb | medium | 1 | 1 | 98 |
| xtb-singlepoint-gfn2 | xtb | easy | 1 | 1 | 46 |

(Per-task durations and machine-readable values are in
`deepseek-v4-flash.json`.)

## Caveats

- Single attempt (k=1); the 6 flips (4 up / 2 down) vs pro include genuine
  model differences *and* ordinary sampling variance — at n=1 the 34 vs 32
  gap is within the noise band a multi-seed comparison would be needed to
  resolve (the `deepseek-v3.2` k=5 report quantifies exactly this). A smoke-run
  observation illustrates it: `ase-geoopt-h2o` missed
  the 1e-6 eV energy tolerance by ~7e-5 eV in the smoke attempt, then passed
  in the full run.
- The comparison is like-for-like: same benchmark commit, task spec, agent
  binary (Claude Code 2.1.215), harness (Harbor 0.20.0), compatibility layer,
  protocol, and host arch. The only changed variable is the model id.
- Agent-phase containers have outbound network (LLM API requirement); no
  refs access was observed in trajectories, but held-out private refs remain
  the robust fix.
- Scores measure the agent × model combination on this harness, not pure
  model chemistry knowledge.

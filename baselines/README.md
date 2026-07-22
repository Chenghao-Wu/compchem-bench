# CompChemBench Baselines

Official leaderboard and baseline run reports. Scores are on the full 40-task
suite (binary reward per task, `1` = pass). Each entry links its full run
report (Markdown) and machine-readable per-task results (JSON).

**Accuracy** is the mean per-task success rate: for each task compute
(passing attempts / attempts), then average over all 40 tasks. With a uniform
number of attempts per task this is equivalent to *total passes / (40 × k)*,
where `k` is the attempts per task. The `k` column records how many attempts
each task received; single-attempt (`k=1`) and multi-seed (`k=5`) entries are
scored by the **same** metric and are directly comparable.

## Leaderboard

| # | Model | Agent | Harness | Date | Benchmark commit | k | Accuracy | easy | medium | hard | Report |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `deepseek-v4-flash` (DeepSeek API) | Claude Code 2.1.215 | Harbor 0.20.0 | 2026-07-21 | `1fb9fa1` | 1 | **85.0%** | 90.0% | 83.3% | 83.3% | [report](deepseek-v4-flash.md) |
| 2 | `deepseek-v4-pro` (DeepSeek API) | Claude Code 2.1.215 | Harbor 0.20.0 | 2026-07-21 | `d18bd2c` | 1 | **80.0%** | 90.0% | 83.3% | 66.7% | [report](deepseek-v4-pro.md) |
| 3 | `deepseek-v3.2` (OpenRouter) | Claude Code 2.1.215 | Harbor 0.20.0 | 2026-07-22 | `aed9c17` | 5 | **71.5%** | 72.0% | 73.3% | 68.3% | [report](deepseek-v3.2.md) |

All three entries ran on the same budget-tuned task spec with an identical agent
(Claude Code 2.1.215), harness (Harbor 0.20.0), and litellm compatibility proxy,
`n_concurrent=6`. The two `k=1` entries take one attempt per task; the
`deepseek-v3.2` entry takes five (200 scored attempts) and reports the same
accuracy metric averaged over its five seeds — which is why its `k=5` score is
comparable to the single-attempt entries rather than an inflated "any-of-five"
number.

Recorded benchmark commits predate the repository's history-squash: `d18bd2c`
(pro) and `aed9c17` (v3.2) are the pre-squash equivalents of the current release
commit, and `1fb9fa1` (flash) is likewise a pre-squash ancestor — the task spec
is identical across them. The flash-vs-pro gap (85.0% vs 80.0%, i.e. 34 vs 32
tasks at `k=1`) is within single-attempt sampling noise; the `deepseek-v3.2`
report quantifies that noise directly from its five seeds (23 of 40 tasks flip
between pass and fail across seeds).

An earlier run of the same agent × `deepseek-v4-pro` combination on the
pre-budget-tuning spec scored 65.0% (26/40) and was superseded by the pro entry
above; its artifacts were removed from the repository, and its numbers are
quoted inline in the pro report for comparison.

## How to submit a new result

1. Run the full suite: `harbor run -p tasks/ -a <agent> -m <model>` on a
   checkout of a tagged/main commit of this repository, x86_64, with
   task-spec'd timeouts. Record the attempts per task (`k`) and the benchmark
   commit. Single-attempt runs use `k=1`; multi-seed runs declare `k` and
   average accuracy over the seeds.
2. Add a run report `<model>[-rN].md` and machine-readable results
   `<model>[-rN].json` following the existing files' format: model/provider,
   agent + version, harness + version, benchmark commit, arch, date, protocol
   (`k`, concurrency), **accuracy** (mean per-task success rate), breakdowns by
   software / difficulty / category, per-task rewards, and any compatibility
   layer used (e.g. an API proxy).
3. **Never commit API keys or credentials** — keys belong in the environment
   only; report files should reference them as `os.environ/…` placeholders.
4. Open a pull request adding your files and a leaderboard row. Report accuracy
   as the mean per-task success rate defined above (not a best-of-k or
   any-of-k upper bound). Results with harness-or-quota errors should disclose
   them; runs are expected to report all 40 tasks.
</content>

# CompChemBench Task Template

A starting scaffold for a new benchmark task. Copy this directory, rename it
`tasks/<software>-<topic>-<qualifier>`, fill in the skeleton files, calibrate
against the pinned image, and register it in `registry.toml`.

> **This directory is not a task.** It lives at the repo root (not under
> `tasks/`) so `.ci/run_all.sh` — which globs `ls tasks` — never tries to CI
> it. A task scaffold here has no `registry.toml` entry and no calibrated
> references, so lint and CI would (correctly) reject it as-is.

## Instantiation checklist

```bash
cp -r task-template tasks/<software>-<topic>-<qualifier>
```

Then, in order:

1. **`task.toml`** — set `metadata.name` to the directory name, pick
   `difficulty` / `capability` / `tags` (see rules below).
2. **`environment/Dockerfile`** — pin the software + version; add
   `COPY assets/ /workspace/assets/` if the task ships inputs.
3. **`environment/assets/`** — drop in every input file the agent needs.
4. **`instruction.md`** — write the task in the goal-oriented style (see the
   `compchem-instruction-writer` skill); document the `results.json`
   `values`/`units` schema.
5. **`solution/solve.sh`** — write the oracle: real execution, no hardcoded
   answers.
6. **`tests/verify.py`** — implement the four verification layers.
7. **`tests/refs.json`** — record calibrated values + tolerances + hashes.
8. **`tests/cheat.sh`** — write an informed forgery that must fail.
9. **`registry.toml`** — add a `[[task]]` entry matching `task.toml` exactly.
10. **Calibrate + CI** (below), then update `DATASET_CARD.md`/`README.md`
    counts and coverage tables.

## The 7 required files

| File | Role | Agent-visible? |
|---|---|---|
| `task.toml` | metadata / verifier / agent / environment config | no |
| `instruction.md` | task description shown to the agent | **yes** |
| `environment/Dockerfile` | pinned software image | indirectly (env) |
| `environment/assets/` | input files copied to `/workspace/assets/` | **yes** |
| `solution/solve.sh` | oracle (real execution) | **no** |
| `tests/test.sh` | entrypoint → `verify.py` → `reward.txt` | no |
| `tests/verify.py` | terminal-state verification | no |
| `tests/refs.json` | references + tolerances + hashes | **no** |
| `tests/cheat.sh` | informed forgery (must fail CI) | no |

`solution/` and `tests/` never enter the image — the `Dockerfile` must not
`COPY` them (lint-enforced). `instruction.md` is the *only* agent-visible
source of the task contract; it must contain no reference values.

## Hard rules (all enforced by `.ci/lint_task.py`)

- **Required files** (7): `task.toml`, `instruction.md`,
  `environment/Dockerfile`, `solution/solve.sh`, `tests/test.sh`,
  `tests/verify.py`, `tests/refs.json`.
- **`task.toml` keys**: `metadata.name/difficulty/capability/tags`,
  `environment.build`, `agent.timeout_sec`, `verifier.timeout_sec`.
- **Difficulty** ∈ `easy | medium | hard`.
- **Capability** ∈ `system-construction | adaptive-convergence |
  property-estimation | scientific-auditing | failure-recovery |
  cross-code-orchestration`. Optional `capabilities_secondary` may not repeat
  the primary and must stay in the vocabulary.
- **Tags**: `tags[0]` must equal `<software>` (the first `-`-segment of the
  task name) and be one of `ase lammps cp2k xtb qe rdkit`; exactly **one**
  method tag from `dft classical-md semi-empirical aimd cheminformatics`;
  **no** retired category tags (`input-prep execution analysis debugging
  workflow`).
- **`registry.toml` ↔ `task.toml`** must agree on `name`, `difficulty`,
  `capability`, `capabilities_secondary`, `tags`, and `path`.
- **`Dockerfile`**: no `COPY` of `tests/` or `solution/` (including
  `COPY --from`), and no `ADD`.
- **`instruction.md`**: no calibrated reference values (lint flags e.g.
  `-76.3 Ha`, `1.2345 eV`); if the task produces `results.json`, the
  instruction must show the `values`/`units` schema and `verify.py` must read
  `results["values"]` / `results["units"]`.
- **`refs.json`**: `calibration_date` (ISO `YYYY-MM-DD`) and `image_digest`
  (`sha256:<64 hex>`) are required; the strings `NEEDS_CALIBRATION` /
  `PENDING_BACKFILL` are rejected anywhere in the file.
- **Asset integrity**: if `verify.py` reads `/workspace/assets`, then
  `refs.json` must pin every consumed asset under `asset_hashes`
  (`"<rel path>" : "sha256:<64 hex>"`), and `environment/<rel path>` must
  exist. `/workspace/assets` is agent-writable, so the verifier re-hashes
  before use (see `qe-dihedral-scan-hexane/tests/verify.py` for the pattern).

## Verification layers (the four-layer contract)

`verify.py` should implement, in order:

1. **Existence** — required output files exist.
2. **Native-output integrity** — the software's own log/restart is present and
   internally consistent (e.g. QE `pw.out` `JOB DONE.` + converged `!` energy).
3. **Numerical tolerance** — `results.json` values match `refs.json` within
   calibrated tolerances.
4. **Cross-verification (L4)** — independently recompute from the agent's final
   state with the in-image software and require the native log, `results.json`,
   and recomputed value to agree. This is what makes fabricated files fail.

`result.json` follows a fixed schema: `{"values": {...}, "units": {...}}`, with
every `values` key mirrored in `units`.

## Calibration protocol

1. Build the image: `docker build --file environment/Dockerfile --tag
   compchem-bench/<name>:ci environment`
2. Record the digest: `docker inspect --format '{{.Id}}' compchem-bench/<name>:ci`
   (the `sha256:` hex) into `refs.json`.
3. Run `solution/solve.sh` **≥ 5 times** in the image; record the spread.
4. `tolerance = max(3 × spread, physical minimum resolution)`. Deterministic
   tasks (zero spread) use the physical minimum resolution.
5. Fill `refs.json` (`arch: x86_64`, `calibration_date`, `image_digest`,
   refs + tolerances) and write a `_calibration_note` documenting the outcome
   — for debugging tasks, record dead ends and their measured energies.
6. Gate it:
   ```bash
   python3 .ci/lint_task.py tasks/<name>   # structural lint
   .ci/run_ci.sh tasks/<name>              # oracle 3/3, null fail, cheat fail
   ```

## Flavor notes

- **Execution / property-estimation** — the agent runs a real calculation and
  reports an observable. L4 recomputes the same quantity from the final state.
- **`failure-recovery` (debug)** — the instruction describes only the symptom
  ("run this calculation"); never name the fault or the fix on any
  agent-visible surface (instruction, asset *contents and filenames*, task dir
  name, registry tags). Difficulty comes from the failure-signature ladder —
  tier 1 aborts helpfully, tier 2 stalls, tier 3 completes with a wrong answer
  — not from fault count. Validate every planted fault empirically before
  adoption; record attractor energies and dead ends in `_calibration_note`.
- **`scientific-auditing`** — nothing fails loudly; the agent must find a flaw
  by reasoning. Recovery fails loudly, auditing fails silently.
- **Asset-bearing** — anything shipped under `environment/assets/` must be
  pinned in `refs.json["asset_hashes"]` and re-hashed by the verifier before
  use. Reusable inputs (potentials, structures) live in `shared/` and are
  copied into the task's `environment/assets/` (see `shared/potentials/README.md`).
- **CP2K / QE images** — pin `OMP_NUM_THREADS=2` (and QE's
  `OMPI_MCA_plm=isolated`) so the binary never oversubscribes the host cores;
  see the QE Dockerfile for the conda-forge toolchain pattern.

## Placeholder convention

Skeleton files use `<ANGLE_BRACKET>` markers and `TODO(author)` comments for
things to replace. Two strings are **banned** in `refs.json` and will not
appear here: `NEEDS_CALIBRATION` and `PENDING_BACKFILL` — leave those out of
real tasks too, or lint fails.

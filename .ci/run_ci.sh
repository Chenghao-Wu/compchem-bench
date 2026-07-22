#!/usr/bin/env bash
# CompChemBench CI runner.
# Requires Docker.  Usage: .ci/run_ci.sh tasks/<task-name>
#
# Pipeline:
#   1. Structural lint
#   2. Build image
#   3. oracle  solve.sh  → must exit 0 and pass 3/3
#   4. null    agent     → must fail
#   5. cheat   agent     → must fail
#
# Exit 0 = all checks pass.

set -euo pipefail

TASK_DIR="${1:?Usage: run_ci.sh tasks/<task-name>}"
TASK_DIR="$(realpath "$TASK_DIR")"
TASK_NAME="$(basename "$TASK_DIR")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== CompChemBench CI: $TASK_NAME ==="

# ── 1. Lint ───────────────────────────────────────────────────────────────────
echo "[1/5] Linting..."
python3 "$SCRIPT_DIR/lint_task.py" "$TASK_DIR"

# ── 2. Build image ────────────────────────────────────────────────────────────
IMAGE_TAG="compchem-bench/${TASK_NAME}:ci"
echo "[2/5] Building image $IMAGE_TAG ..."
docker build \
  --file "$TASK_DIR/environment/Dockerfile" \
  --tag "$IMAGE_TAG" \
  --build-arg TASK_DIR="$TASK_DIR" \
  "$TASK_DIR/environment"

# ── 3. Oracle baseline (3/3 must pass, solve.sh itself must exit 0) ──────────
echo "[3/5] Oracle baseline (3 runs, solve.sh exit code gated)..."
# Copy solution into the image run context
docker_run_oracle() {
  local cid
  cid=$(docker create --rm=false --cpus=2 --memory=4g --network=none \
        --entrypoint=/bin/bash --workdir=/workspace "$IMAGE_TAG" \
        -c "mkdir -p /workspace /logs/verifier; bash /solution/solve.sh; echo \$? > /logs/solve_exit_code.txt; bash /tests/test.sh")
  docker cp "$TASK_DIR/tests"   "$cid:/tests"
  docker cp "$TASK_DIR/solution" "$cid:/solution"
  docker start -a "$cid" || true
  local reward solve_exit
  docker cp "$cid:/logs/verifier/reward.txt" "/tmp/reward.$cid.txt" >/dev/null 2>&1 || true
  reward=$(cat "/tmp/reward.$cid.txt" 2>/dev/null || echo "0")
  reward="${reward//[[:space:]]/}"
  docker cp "$cid:/logs/solve_exit_code.txt" "/tmp/solve_exit.$cid.txt" >/dev/null 2>&1 || true
  solve_exit=$(cat "/tmp/solve_exit.$cid.txt" 2>/dev/null || echo "missing")
  solve_exit="${solve_exit//[[:space:]]/}"
  docker rm -f "$cid" >/dev/null 2>&1 || true
  rm -f "/tmp/reward.$cid.txt" "/tmp/solve_exit.$cid.txt"
  if [ "$solve_exit" != "0" ]; then
    echo "  solve.sh exited non-zero (exit=$solve_exit) — oracle script must run clean" >&2
    return 1
  fi
  [ "$reward" = "1" ] && return 0 || return 1
}

oracle_pass=0
for i in 1 2 3; do
  echo "  [oracle run $i/3]"
  if docker_run_oracle; then
    echo "  [oracle run $i/3] pass"
    oracle_pass=$((oracle_pass + 1))
  else
    echo "  [oracle run $i/3] FAIL" >&2
  fi
done
if [ "$oracle_pass" -lt 3 ]; then
  echo "[3/5] FAIL: oracle only passed $oracle_pass/3" >&2
  exit 1
fi
echo "[3/5] OK: oracle 3/3"

# ── 4. Null agent (must fail) ─────────────────────────────────────────────────
echo "[4/5] Null agent baseline..."
NULL_INIT="$(mktemp /tmp/null_init.XXXXXX.sh)"
echo "# null agent: do nothing" > "$NULL_INIT"
NULL_CID=$(docker create --rm=false --cpus=2 --memory=4g --network=none \
           --entrypoint=/bin/bash --workdir=/workspace "$IMAGE_TAG" \
           -c "mkdir -p /workspace /logs/verifier; bash /tests/test.sh")
docker cp "$TASK_DIR/tests" "$NULL_CID:/tests"
docker start -a "$NULL_CID" || true
docker cp "$NULL_CID:/logs/verifier/reward.txt" "/tmp/reward.$NULL_CID.txt" >/dev/null 2>&1 || true
NULL_REWARD=$(cat "/tmp/reward.$NULL_CID.txt" 2>/dev/null || echo "0")
NULL_REWARD="${NULL_REWARD//[[:space:]]/}"
docker rm -f "$NULL_CID" >/dev/null 2>&1 || true
rm -f "$NULL_INIT"

if [ "$NULL_REWARD" != "0" ]; then
  echo "[4/5] FAIL: null agent passed (reward=$NULL_REWARD) — verifier is too lenient" >&2
  exit 1
fi
echo "[4/5] OK: null agent fails as expected"

# ── 5. Cheat scripts (every tests/cheat*.sh must fail) ──────────────────────
echo "[5/5] Cheat agent baseline..."
shopt -s nullglob
CHEAT_SCRIPTS=("$TASK_DIR"/tests/cheat*.sh)
shopt -u nullglob
if [ ${#CHEAT_SCRIPTS[@]} -eq 0 ]; then
  echo "  [cheat] No cheat*.sh found, skipping (add tests/cheat.sh to enable)" >&2
else
  for CHEAT_SCRIPT in "${CHEAT_SCRIPTS[@]}"; do
    echo "  [cheat] $(basename "$CHEAT_SCRIPT")"
    CHEAT_CID=$(docker create --rm=false --cpus=2 --memory=4g --network=none \
                --entrypoint=/bin/bash --workdir=/workspace "$IMAGE_TAG" \
                -c "mkdir -p /workspace /logs/verifier; bash /cheat.sh; bash /tests/test.sh")
    docker cp "$TASK_DIR/tests" "$CHEAT_CID:/tests"
    docker cp "$CHEAT_SCRIPT"   "$CHEAT_CID:/cheat.sh"
    docker start -a "$CHEAT_CID" || true
    docker cp "$CHEAT_CID:/logs/verifier/reward.txt" "/tmp/reward.$CHEAT_CID.txt" >/dev/null 2>&1 || true
    CHEAT_REWARD=$(cat "/tmp/reward.$CHEAT_CID.txt" 2>/dev/null || echo "0")
    CHEAT_REWARD="${CHEAT_REWARD//[[:space:]]/}"
    docker rm -f "$CHEAT_CID" >/dev/null 2>&1 || true

    if [ "$CHEAT_REWARD" != "0" ]; then
      echo "[5/5] FAIL: $(basename "$CHEAT_SCRIPT") passed (reward=$CHEAT_REWARD) — anti-cheat checks insufficient" >&2
      exit 1
    fi
  done
  echo "[5/5] OK: ${#CHEAT_SCRIPTS[@]} cheat script(s) all fail as expected"
fi

echo ""
echo "=== ALL CI CHECKS PASSED: $TASK_NAME ==="

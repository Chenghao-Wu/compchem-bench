#!/usr/bin/env bash
# CompChemBench CI runner.
# Requires Docker. Usage: .ci/run_ci.sh tasks/<task-name>
#
# Pipeline:
#   1. Structural lint
#   2. Build image
#   3. oracle solution: must exit 0 and pass 3/3
#   4. null agent: must fail
#   5. informed-cheat agent: must fail
#
# Network policy:
#   - task.toml network=false: agent and verifier remain offline.
#   - task.toml network=true: agent/oracle uses the bridge network, which is
#     disconnected before tests/test.sh starts.
#   - null and cheat baselines are always offline.

set -euo pipefail

TASK_DIR="${1:?Usage: .ci/run_ci.sh tasks/<task-name>}"
TASK_DIR="$(realpath "$TASK_DIR")"
TASK_NAME="$(basename "$TASK_DIR")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mapfile -t TASK_RUNTIME < <(
  python3 - "$TASK_DIR/task.toml" <<'PY'
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

with open(sys.argv[1], "rb") as handle:
    environment = tomllib.load(handle)["environment"]

print(environment["cpus"])
print(environment["memory_gb"])
print("bridge" if environment["network"] else "none")
print("true" if environment["network"] else "false")
PY
)
TASK_CPUS="${TASK_RUNTIME[0]}"
TASK_MEMORY="${TASK_RUNTIME[1]}g"
AGENT_NETWORK_MODE="${TASK_RUNTIME[2]}"
TASK_NETWORK_ENABLED="${TASK_RUNTIME[3]}"

echo "=== CompChemBench CI: $TASK_NAME ==="
echo "Runtime: cpus=$TASK_CPUS memory=$TASK_MEMORY agent_network=$AGENT_NETWORK_MODE verifier_network=none"

echo "[1/5] Linting..."
python3 "$SCRIPT_DIR/lint_task.py" "$TASK_DIR"

IMAGE_TAG="compchem-bench/${TASK_NAME}:ci"
echo "[2/5] Building image $IMAGE_TAG ..."
docker build \
  --file "$TASK_DIR/environment/Dockerfile" \
  --tag "$IMAGE_TAG" \
  --build-arg TASK_DIR="$TASK_DIR" \
  "$TASK_DIR/environment"

disconnect_agent_network() {
  local cid="$1"
  if [ "$TASK_NETWORK_ENABLED" = "true" ]; then
    docker network disconnect bridge "$cid"
  fi
}

docker_run_oracle() {
  local cid reward solve_exit
  cid=$(docker create --rm=false \
        --cpus="$TASK_CPUS" \
        --memory="$TASK_MEMORY" \
        --network="$AGENT_NETWORK_MODE" \
        --entrypoint=/bin/bash \
        --workdir=/workspace \
        "$IMAGE_TAG" \
        -c "mkdir -p /workspace /logs/verifier; sleep infinity")
  docker cp "$TASK_DIR/tests" "$cid:/tests"
  docker cp "$TASK_DIR/solution" "$cid:/solution"
  docker start "$cid" >/dev/null

  if docker exec "$cid" bash /solution/solve.sh; then
    solve_exit=0
  else
    solve_exit=$?
  fi

  if ! disconnect_agent_network "$cid"; then
    echo "  failed to disconnect agent network before verifier" >&2
    docker rm -f "$cid" >/dev/null 2>&1 || true
    return 1
  fi

  docker exec "$cid" bash /tests/test.sh || true
  docker cp "$cid:/logs/verifier/reward.txt" "/tmp/reward.$cid.txt" >/dev/null 2>&1 || true
  reward=$(cat "/tmp/reward.$cid.txt" 2>/dev/null || echo "0")
  reward="${reward//[[:space:]]/}"
  docker rm -f "$cid" >/dev/null 2>&1 || true
  rm -f "/tmp/reward.$cid.txt"

  if [ "$solve_exit" != "0" ]; then
    echo "  solve.sh exited non-zero (exit=$solve_exit) - oracle script must run clean" >&2
    return 1
  fi
  [ "$reward" = "1" ]
}

echo "[3/5] Oracle baseline (3 runs, solve.sh exit code gated)..."
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

echo "[4/5] Null agent baseline..."
NULL_CID=$(docker create --rm=false \
           --cpus="$TASK_CPUS" \
           --memory="$TASK_MEMORY" \
           --network=none \
           --entrypoint=/bin/bash \
           --workdir=/workspace \
           "$IMAGE_TAG" \
           -c "mkdir -p /workspace /logs/verifier; sleep infinity")
docker cp "$TASK_DIR/tests" "$NULL_CID:/tests"
docker start "$NULL_CID" >/dev/null
docker exec "$NULL_CID" bash /tests/test.sh || true
docker cp "$NULL_CID:/logs/verifier/reward.txt" "/tmp/reward.$NULL_CID.txt" >/dev/null 2>&1 || true
NULL_REWARD=$(cat "/tmp/reward.$NULL_CID.txt" 2>/dev/null || echo "0")
NULL_REWARD="${NULL_REWARD//[[:space:]]/}"
docker rm -f "$NULL_CID" >/dev/null 2>&1 || true
rm -f "/tmp/reward.$NULL_CID.txt"

if [ "$NULL_REWARD" != "0" ]; then
  echo "[4/5] FAIL: null agent passed (reward=$NULL_REWARD) - verifier is too lenient" >&2
  exit 1
fi
echo "[4/5] OK: null agent fails as expected"

echo "[5/5] Cheat agent baseline..."
shopt -s nullglob
CHEAT_SCRIPTS=("$TASK_DIR"/tests/cheat*.sh)
shopt -u nullglob
if [ ${#CHEAT_SCRIPTS[@]} -eq 0 ]; then
  echo "  [cheat] No cheat*.sh found, skipping (add tests/cheat.sh to enable)" >&2
else
  for CHEAT_SCRIPT in "${CHEAT_SCRIPTS[@]}"; do
    echo "  [cheat] $(basename "$CHEAT_SCRIPT")"
    CHEAT_CID=$(docker create --rm=false \
                --cpus="$TASK_CPUS" \
                --memory="$TASK_MEMORY" \
                --network=none \
                --entrypoint=/bin/bash \
                --workdir=/workspace \
                "$IMAGE_TAG" \
                -c "mkdir -p /workspace /logs/verifier; sleep infinity")
    docker cp "$TASK_DIR/tests" "$CHEAT_CID:/tests"
    docker cp "$CHEAT_SCRIPT" "$CHEAT_CID:/cheat.sh"
    docker start "$CHEAT_CID" >/dev/null
    docker exec "$CHEAT_CID" bash /cheat.sh
    docker exec "$CHEAT_CID" bash /tests/test.sh || true
    docker cp "$CHEAT_CID:/logs/verifier/reward.txt" "/tmp/reward.$CHEAT_CID.txt" >/dev/null 2>&1 || true
    CHEAT_REWARD=$(cat "/tmp/reward.$CHEAT_CID.txt" 2>/dev/null || echo "0")
    CHEAT_REWARD="${CHEAT_REWARD//[[:space:]]/}"
    docker rm -f "$CHEAT_CID" >/dev/null 2>&1 || true
    rm -f "/tmp/reward.$CHEAT_CID.txt"

    if [ "$CHEAT_REWARD" != "0" ]; then
      echo "[5/5] FAIL: $(basename "$CHEAT_SCRIPT") passed (reward=$CHEAT_REWARD) - anti-cheat checks insufficient" >&2
      exit 1
    fi
  done
  echo "[5/5] OK: ${#CHEAT_SCRIPTS[@]} cheat script(s) all fail as expected"
fi

echo ""
echo "=== ALL CI CHECKS PASSED: $TASK_NAME ==="

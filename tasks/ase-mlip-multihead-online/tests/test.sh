#!/usr/bin/env bash
# Test entrypoint for ase-mlip-multihead-online.
set -euo pipefail

WORKSPACE="${1:-/workspace}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="/logs/verifier"

mkdir -p "$LOGS_DIR"

echo "=== Running verifier for ase-mlip-multihead-online ==="
echo "Workspace: $WORKSPACE"

if python "$SCRIPT_DIR/verify.py" "$WORKSPACE" > "$LOGS_DIR/verify.log" 2>&1; then
    echo "1" > "$LOGS_DIR/reward.txt"
    echo "PASS"
else
    echo "0" > "$LOGS_DIR/reward.txt"
    echo "FAIL"
fi

cat "$LOGS_DIR/verify.log"

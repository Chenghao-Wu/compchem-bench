#!/usr/bin/env bash
# Regenerates the failed_run.out artifacts for qe-error-diagnose by REALLY
# running the three broken inputs inside this task's image (QE is open
# source — no fabricated assets). The committed failed_run.out files under
# environment/assets/case*/ were produced by exactly this script.
#
# Usage (from the repo root, image already built):
#   cid=$(docker create compchem-bench/qe-error-diagnose:ci \
#         bash /work/generate_assets.sh)
#   docker cp tasks/qe-error-diagnose/environment "$cid:/work"
#   docker start -a "$cid" || true
#   docker cp "$cid:/work/assets" tasks/qe-error-diagnose/environment/
set -euo pipefail
cd "$(dirname "$0")"

for case in case1_pseudo case2_cell case3_scf; do
  work=$(mktemp -d)
  cp assets/$case/case*.in "$work/input.in"
  cp -r assets/$case/pseudo "$work/pseudo"
  # broken inputs are EXPECTED to fail — capture the log, never abort
  (cd "$work" && pw.x -in input.in > failed_run.out 2>&1) || true
  cp "$work/failed_run.out" "assets/$case/failed_run.out"
  rm -rf "$work"
  echo "regenerated assets/$case/failed_run.out"
done

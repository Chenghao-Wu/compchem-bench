#!/usr/bin/env bash
# Full 42-task CI re-run driver. Runs .ci/run_ci.sh per task with
# limited parallelism, logs per task, prints a PASS/FAIL summary.
set -u
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
LOGDIR="$REPO_ROOT/.ci/logs-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOGDIR"
echo "Logs: $LOGDIR"

# Modified/high-priority tasks first for early feedback, then the rest.
PRIORITY="lammps-lj-melt cp2k-h2o-sp rdkit-conformer-mmff ase-format-convert ase-neb-adatom lammps-data-build lammps-eam-lattice cp2k-basis-convergence xtb-singlepoint-gfn2 qe-relax-co"
ALL=$(ls tasks)
TASKS="$PRIORITY"
for t in $ALL; do
  case " $PRIORITY " in *" $t "*) ;; *) TASKS="$TASKS $t";; esac
done

run_one() {
  local t="$1"
  if bash .ci/run_ci.sh "tasks/$t" > "$LOGDIR/$t.log" 2>&1; then
    echo "PASS $t"
  else
    echo "FAIL $t"
  fi
}

export -f run_one
export LOGDIR

printf '%s\n' $TASKS | xargs -P 6 -I{} bash -c 'run_one "$@"' _ {} > "$LOGDIR/summary.txt"
echo "===== SUMMARY ====="
sort "$LOGDIR/summary.txt" | tee "$LOGDIR/summary.sorted.txt"
echo "PASS count: $(grep -c '^PASS' "$LOGDIR/summary.txt") / 42"

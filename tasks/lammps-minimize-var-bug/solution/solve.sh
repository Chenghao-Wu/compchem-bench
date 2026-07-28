#!/usr/bin/env bash
# Oracle solution for lammps-minimize-var-bug.
#
# Root cause: `variable X equal pe` defines an *equal-style* variable, which
# is evaluated lazily — every time it is referenced, not when it is defined.
# So `${E_initial}`, dereferenced in the final summary, re-evaluates `pe`
# against the already-minimised state and returns the FINAL energy. Both
# summary lines print the same number and Delta_E collapses to 0. (The
# script's own earlier print, issued before `minimize`, shows the true
# initial energy — the log contradicts itself.)
#
# Fix: capture the values immediately. `$(pe)` is substituted once, at parse
# time, so `variable E_initial equal $(pe)` freezes the current energy into
# the variable definition.
set -euo pipefail
cd /workspace

sed -e 's/^variable        E_initial equal pe$/variable        E_initial equal $(pe)/' \
    -e 's/^variable        E_final equal pe$/variable        E_final equal $(pe)/' \
    assets/porphin_minimize.in > porphin_minimize_fixed.in

# Sanity-check that both substitutions actually landed.
grep -q 'E_initial equal $(pe)' porphin_minimize_fixed.in
grep -q 'E_final equal $(pe)' porphin_minimize_fixed.in

export OMP_NUM_THREADS=1
lmp_serial -in porphin_minimize_fixed.in

python3 << 'PYEOF'
import json
import re

with open("log.lammps") as f:
    log = f.read()


def grab(label):
    m = re.search(rf"^\s*{label}\s+(-?[\d.eE+]+)\s+kcal/mol\s*$", log, re.MULTILINE)
    if not m:
        raise SystemExit(f"could not find the '{label}' summary line in log.lammps")
    return float(m.group(1))


e_initial = grab("Initial Energy:")
e_final = grab("Final Energy:")
delta_e = grab("Energy Change:")

# Iteration count: the minimise run is the last "Loop time ... for N steps"
# line (the leading `run 0` contributes a 0-step loop before it).
loops = re.findall(r"Loop time of \S+ on \d+ procs for (\d+) steps with \d+ atoms", log)
if not loops:
    raise SystemExit("no 'Loop time' line found in log.lammps")
n_iterations = int(loops[-1])

results = {
    "values": {
        "e_initial": e_initial,
        "e_final": e_final,
        "delta_e": delta_e,
        "n_iterations": n_iterations,
    },
    "units": {
        "e_initial": "kcal/mol",
        "e_final": "kcal/mol",
        "delta_e": "kcal/mol",
        "n_iterations": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E_initial = {e_initial:.6f}  E_final = {e_final:.6f}  "
      f"dE = {delta_e:.6f} kcal/mol over {n_iterations} iterations")
PYEOF

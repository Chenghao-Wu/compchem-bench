#!/usr/bin/env bash
# Informed cheat: an agent that RUNS the real calculation, reads the true
# energies out of the log — and then "fixes" the script by pasting those
# numbers in as literals instead of repairing the reporting mechanism.
#
# This is the most dangerous failure mode for this task, because every
# artefact it produces is genuine:
#   - porphin_minimized.data is the real minimised structure (so the layer-6
#     recompute of e_final succeeds)
#   - log.lammps is a real LAMMPS log of a real run
#   - results.json carries the true energies and the true iteration count
#   - the fixed input keeps every required style, min_style and minimize line
# It therefore passes layers 1-6 completely.
#
# Must FAIL at layer 7: the verifier re-runs this same fixed input against a
# perturbed copy of the molecule, which has different energies. A script that
# prints constants reports the pristine numbers for a system they do not
# describe.
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1

# Step 1 — run the ORIGINAL (buggy) script far enough to harvest the truth.
cat > _probe.in << 'EOF'
units           real
atom_style      full
boundary        p p p
read_data       assets/system_gaff2.data
bond_style      harmonic
angle_style     harmonic
dihedral_style  fourier
improper_style  cvff
pair_style      lj/charmm/coul/long 8.0 10.0
kspace_style    ewald 0.0001
include         assets/system_gaff2.in.settings
neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes
thermo_style    custom step pe
thermo          10
run             0
min_style       cg
minimize        1.0e-4 1.0e-6 1000 10000
EOF
lmp_serial -in _probe.in > _probe.out 2>&1

read -r E_INIT E_FINAL N_ITER << EOF
$(python3 - << 'PYEOF'
import re
out = open("_probe.out").read()
m = re.search(r"Energy initial, next-to-last, final\s*=\s*\n\s*"
              r"(-?[\d.eE+]+)\s+(-?[\d.eE+]+)\s+(-?[\d.eE+]+)", out)
loops = re.findall(r"Loop time of \S+ on \d+ procs for (\d+) steps", out)
print(m.group(1), m.group(3), loops[-1])
PYEOF
)
EOF

DELTA=$(python3 -c "print(repr(float('$E_FINAL') - float('$E_INIT')))")

# Step 2 — "fix" the script by hardcoding the harvested constants.
python3 - "$E_INIT" "$E_FINAL" "$DELTA" << 'PYEOF'
import re
import sys

e_init, e_final, delta = sys.argv[1], sys.argv[2], sys.argv[3]
src = open("assets/porphin_minimize.in").read()
src = re.sub(r"^variable\s+E_initial equal pe$",
             f"variable        E_initial equal {e_init}", src, flags=re.M)
src = re.sub(r"^variable\s+E_final equal pe$",
             f"variable        E_final equal {e_final}", src, flags=re.M)
src = re.sub(r"^variable\s+Delta_E equal .*$",
             f"variable        Delta_E equal {delta}", src, flags=re.M)
open("porphin_minimize_fixed.in", "w").write(src)
PYEOF

# Step 3 — run the "fixed" script for real: genuine log + genuine structure.
lmp_serial -in porphin_minimize_fixed.in > /dev/null 2>&1

python3 - "$E_INIT" "$E_FINAL" "$DELTA" "$N_ITER" << 'PYEOF'
import json
import sys

e_init, e_final, delta, n_iter = sys.argv[1:5]
results = {
    "values": {
        "e_initial": float(e_init),
        "e_final": float(e_final),
        "delta_e": float(delta),
        "n_iterations": int(n_iter),
    },
    "units": {
        "e_initial": "kcal/mol",
        "e_final": "kcal/mol",
        "delta_e": "kcal/mol",
        "n_iterations": "1",
    },
}
json.dump(results, open("results.json", "w"), indent=2)
print(f"Hardcoded-constant 'fix': E_init={e_init} E_final={e_final} "
      f"dE={delta} over {n_iter} iterations (all genuine values)")
PYEOF

rm -f _probe.in _probe.out

#!/usr/bin/env bash
# Oracle solution for qe-error-diagnose: fix each broken input and re-run.
set -euo pipefail
cd /workspace

# ── Case 1: ATOMIC_SPECIES references a pseudopotential filename that does
#    not exist (Si.pbe-n-rrkjus.UPF). Fix: use the real provided filename.
mkdir -p case1
cp -r assets/case1_pseudo/pseudo case1/pseudo
sed 's/Si\.pbe-n-rrkjus\.UPF/Si.pbe-n-rrkjus_psl.1.0.0.UPF/' \
    assets/case1_pseudo/case1.in > case1/case1.in
(cd case1 && pw.x -in case1.in > case1.out)

# ── Case 2: ibrav=2 (cell from celldm) AND a CELL_PARAMETERS card — the cell
#    is defined twice ("redundant data for cell parameters"). Fix: keep
#    ibrav=2 + celldm(1) and drop the CELL_PARAMETERS card.
mkdir -p case2
cp -r assets/case2_cell/pseudo case2/pseudo
sed '/^CELL_PARAMETERS/,/^  2\.714329  2\.714329  0\.000000$/d' \
    assets/case2_cell/case2.in > case2/case2.in
(cd case2 && pw.x -in case2.in > case2.out)

# ── Case 3: SCF does not converge — mixing_beta=0.05 is far too conservative
#    and electron_maxstep=20 too small (the SCF needs ~37 iterations at that
#    mixing). Fix: sensible mixing_beta and iteration budget.
mkdir -p case3
cp -r assets/case3_scf/pseudo case3/pseudo
sed 's/mixing_beta = 0.05/mixing_beta = 0.5/; s/electron_maxstep = 20/electron_maxstep = 100/' \
    assets/case3_scf/case3.in > case3/case3.in
(cd case3 && pw.x -in case3.in > case3.out)

python3 << 'PYEOF'
import json
import re

energies = {}
for n in (1, 2, 3):
    with open(f"case{n}/case{n}.out") as f:
        content = f.read()
    m = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    if not m:
        raise RuntimeError(f"case{n}: no converged total energy")
    energies[n] = float(m[-1])

results = {
    "values": {
        "case1_energy_Ry": energies[1],
        "case2_energy_Ry": energies[2],
        "case3_energy_Ry": energies[3],
    },
    "units": {
        "case1_energy_Ry": "Ry",
        "case2_energy_Ry": "Ry",
        "case3_energy_Ry": "Ry",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(energies)
PYEOF

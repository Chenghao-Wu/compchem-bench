#!/usr/bin/env bash
# Oracle solution for cp2k-input-debug.
set -euo pipefail
cd /workspace

# The three errors in broken_ch4_sp.inp:
#   1. missing "&END SCF" (the &SCF section is never closed)
#   2. basis set typo "DZVP-MOLOPT-SR-GTHH" -> "DZVP-MOLOPT-SR-GTH"
#   3. cutoff unit "CUTOFF [eV] 300" -> "CUTOFF 300" (300 Ha as intended)
cp /workspace/assets/broken_ch4_sp.inp ./fixed.inp
sed -i 's/DZVP-MOLOPT-SR-GTHH/DZVP-MOLOPT-SR-GTH/' fixed.inp
sed -i 's/CUTOFF \[eV\] 300/CUTOFF 300/' fixed.inp
sed -i '/MAX_SCF 50/a\    \&END SCF' fixed.inp

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

mpirun -np 1 cp2k -i fixed.inp -o ch4_sp.out

python3 << 'PYEOF'
import json
import re

with open("ch4_sp.out") as f:
    content = f.read()

energy_matches = re.findall(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
if not energy_matches:
    raise RuntimeError("No energy found in output")
total_energy = float(energy_matches[-1])

scf_converged = "SCF run converged" in content

results = {
    "values": {
        "total_energy": total_energy,
        "scf_converged": scf_converged,
    },
    "units": {
        "total_energy": "Ha",
        "scf_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={total_energy:.8f} Ha, scf_converged={scf_converged}")
PYEOF

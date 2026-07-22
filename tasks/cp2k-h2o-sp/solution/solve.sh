#!/usr/bin/env bash
# Oracle solution for cp2k-h2o-sp.
set -euo pipefail
cd /workspace

cp /workspace/assets/h2o_sp.inp ./h2o_sp.inp

# Basis/potential files live in the CP2K data directory
ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

# Run CP2K (single MPI rank for reproducibility; OT can vary with MPI count)
mpirun -np 1 cp2k -i h2o_sp.inp -o h2o_sp.out

python3 << 'PYEOF'
import json
import re

with open("h2o_sp.out") as f:
    content = f.read()

# Extract total energy — CP2K prints:
#   ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:    -17.21967105...
energy_match = re.search(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
if not energy_match:
    raise RuntimeError("Could not find total energy in CP2K output")

total_energy = float(energy_match.group(1))

# SCF convergence
scf_converged = "SCF run converged" in content or "converged in" in content.lower()

# SCF iteration count
scf_steps = len(re.findall(r"^\s+\d+\s+[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+", content, re.MULTILINE))

results = {
    "values": {
        "total_energy": total_energy,
        "scf_converged": scf_converged,
        "n_scf_steps": scf_steps,
    },
    "units": {
        "total_energy": "Ha",
        "scf_converged": "1",
        "n_scf_steps": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Energy: {total_energy:.8f} Ha, SCF converged: {scf_converged}, steps: {scf_steps}")
PYEOF

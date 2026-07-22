#!/usr/bin/env bash
# Oracle solution for qe-scf-si.
set -euo pipefail
cd /workspace

cp /workspace/assets/si_scf.in ./si_scf.in
cp -r /workspace/assets/pseudo ./pseudo

# Single MPI rank (singleton via OMPI_MCA_plm=isolated, set in the image);
# OMP threads pinned to the 2-CPU quota by the image ENV.
pw.x -in si_scf.in > si_scf.out

python3 << 'PYEOF'
import json
import re

with open("si_scf.out") as f:
    content = f.read()

energy_matches = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
if not energy_matches:
    raise RuntimeError("No '! total energy' line found")
total_energy = float(energy_matches[-1])

scf_converged = "convergence has been achieved" in content
n_iterations = len(re.findall(r"iteration #\s*\d+", content))

results = {
    "values": {
        "total_energy": total_energy,
        "scf_converged": scf_converged,
        "n_scf_iterations": n_iterations,
    },
    "units": {
        "total_energy": "Ry",
        "scf_converged": "1",
        "n_scf_iterations": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={total_energy:.8f} Ry, converged={scf_converged}, iterations={n_iterations}")
PYEOF

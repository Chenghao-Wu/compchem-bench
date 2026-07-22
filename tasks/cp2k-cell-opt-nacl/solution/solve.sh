#!/usr/bin/env bash
# Oracle solution for cp2k-cell-opt-nacl.
set -euo pipefail
cd /workspace

cp /workspace/assets/nacl_cellopt.inp ./nacl_cellopt.inp

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

mpirun -np 1 cp2k -i nacl_cellopt.inp -o nacl_cellopt.out

python3 << 'PYEOF'
import json
import re

with open("nacl_cellopt.out") as f:
    content = f.read()

# Final energy: last ENERGY| line
energy_matches = re.findall(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
if not energy_matches:
    raise RuntimeError("No energy found in output")
final_energy = float(energy_matches[-1])

cell_converged = "GEOMETRY OPTIMIZATION COMPLETED" in content
n_steps = len(re.findall(r"OPTIMIZATION STEP:", content))

# Final lattice constant: last CELL| Vector a magnitude
#   CELL| Vector a [angstrom]:       5.823     0.000     0.000   |a| =     5.822908
a_matches = re.findall(r"CELL\| Vector a \[angstrom\]:.*?\|a\| =\s*([\d.]+)", content)
if not a_matches:
    raise RuntimeError("No CELL| Vector a line found")
a0 = float(a_matches[-1])

results = {
    "values": {
        "final_energy": final_energy,
        "lattice_constant": a0,
        "cell_opt_converged": cell_converged,
        "n_opt_steps": n_steps,
    },
    "units": {
        "final_energy": "Ha",
        "lattice_constant": "Å",
        "cell_opt_converged": "1",
        "n_opt_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={final_energy:.8f} Ha, a0={a0:.6f} Å, converged={cell_converged}, steps={n_steps}")
PYEOF

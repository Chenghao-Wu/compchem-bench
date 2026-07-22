#!/usr/bin/env bash
# Oracle solution for cp2k-geoopt-nh3.
set -euo pipefail
cd /workspace

cp /workspace/assets/nh3_geoopt.inp ./nh3_geoopt.inp

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

mpirun -np 1 cp2k -i nh3_geoopt.inp -o nh3_geoopt.out

python3 << 'PYEOF'
import json
import re
import os
import numpy as np

with open("nh3_geoopt.out") as f:
    content = f.read()

# Final energy: last occurrence of the ENERGY| line, e.g.
#   ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:    -11.73786935...
energy_matches = re.findall(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
if not energy_matches:
    raise RuntimeError("No energy found in output")
final_energy = float(energy_matches[-1])

# Geometry convergence
geo_converged = "GEOMETRY OPTIMIZATION COMPLETED" in content

# Count geometry steps
n_geo = len(re.findall(r"OPTIMIZATION STEP:", content))

# Final geometry from the trajectory file (Angstrom)
xyz_file = "nh3_geoopt-pos-1.xyz"
if os.path.exists(xyz_file):
    from ase.io import read
    atoms = read(xyz_file, index=-1)
    n_pos = atoms.positions[0]
    h_pos = atoms.positions[1]
    nh_bond = float(np.linalg.norm(h_pos - n_pos))
else:
    # Parse from output: last ATOMIC POSITIONS block (Bohr)
    coord_blocks = re.findall(
        r"ATOMIC POSITIONS.*?\n((?:\s+\w+\s+\w+\s+[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+\n)+)",
        content
    )
    if not coord_blocks:
        raise RuntimeError("No coordinate block found")
    last_block = coord_blocks[-1].strip().splitlines()
    positions = []
    for line in last_block:
        parts = line.split()
        positions.append([float(parts[2]), float(parts[3]), float(parts[4])])
    pos = np.array(positions)
    BOHR_TO_A = 0.529177
    nh_bond = float(np.linalg.norm(pos[1] - pos[0])) * BOHR_TO_A

results = {
    "values": {
        "final_energy": final_energy,
        "nh_bond_length": nh_bond,
        "geo_opt_converged": geo_converged,
        "n_geo_steps": n_geo,
    },
    "units": {
        "final_energy": "Ha",
        "nh_bond_length": "Å",
        "geo_opt_converged": "1",
        "n_geo_steps": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={final_energy:.8f} Ha, N-H={nh_bond:.4f} Å, converged={geo_converged}, steps={n_geo}")
PYEOF

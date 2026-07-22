#!/usr/bin/env bash
# Oracle solution for qe-relax-co.
set -euo pipefail
cd /workspace

cp /workspace/assets/co_relax.in ./co_relax.in
cp -r /workspace/assets/pseudo ./pseudo

# Single MPI rank (singleton via OMPI_MCA_plm=isolated, set in the image);
# OMP threads pinned to the 2-CPU quota by the image ENV.
pw.x -in co_relax.in > co_relax.out

python3 << 'PYEOF'
import json
import math
import re

with open("co_relax.out") as f:
    content = f.read()

m_e = re.search(r"Final energy\s*=\s*([-\d.]+)\s+Ry", content)
if not m_e:
    raise RuntimeError("No 'Final energy' line found")
final_energy = float(m_e.group(1))

m_bfgs = re.search(r"bfgs converged in\s+(\d+)\s+scf cycles and\s+(\d+)\s+bfgs steps", content)
relax_converged = m_bfgs is not None
n_bfgs = int(m_bfgs.group(2)) if m_bfgs else 0

m_geo = re.search(
    r"Begin final coordinates\s+ATOMIC_POSITIONS \(angstrom\)\s+((?:\s*\w+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n)+)\s*End final coordinates",
    content)
if not m_geo:
    raise RuntimeError("No final ATOMIC_POSITIONS block found")
pos = {}
for line in m_geo.group(1).strip().splitlines():
    p = line.split()
    pos[p[0]] = (float(p[1]), float(p[2]), float(p[3]))
bond = math.dist(pos["C"], pos["O"])

results = {
    "values": {
        "final_energy": final_energy,
        "co_bond_length": bond,
        "relax_converged": relax_converged,
        "n_bfgs_steps": n_bfgs,
    },
    "units": {
        "final_energy": "Ry",
        "co_bond_length": "Å",
        "relax_converged": "1",
        "n_bfgs_steps": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={final_energy:.8f} Ry, C-O={bond:.4f} Å, converged={relax_converged}, bfgs_steps={n_bfgs}")
PYEOF

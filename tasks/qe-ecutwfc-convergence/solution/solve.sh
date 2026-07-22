#!/usr/bin/env bash
# Oracle solution for qe-ecutwfc-convergence.
set -euo pipefail
cd /workspace

cp -r /workspace/assets/pseudo ./pseudo

for ecut in 20 30 40 50 60; do
cat > si_ecut${ecut}.in << EOF
&CONTROL
  calculation = 'scf'
  prefix = 'pwscf'
  outdir = './outdir'
  pseudo_dir = './pseudo'
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.26
  nat = 2
  ntyp = 1
  ecutwfc = ${ecut}.0
  ecutrho = 480.0
/
&ELECTRONS
  conv_thr = 1.0d-10
  mixing_beta = 0.7
/
ATOMIC_SPECIES
  Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS alat
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  4 4 4 1 1 1
EOF
  rm -rf outdir
  pw.x -in si_ecut${ecut}.in > si_ecut${ecut}.out
done

python3 << 'PYEOF'
import json
import re

grid = [20.0, 30.0, 40.0, 50.0, 60.0]
energies = []
for ecut in (20, 30, 40, 50, 60):
    with open(f"si_ecut{ecut}.out") as f:
        content = f.read()
    m = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    if not m:
        raise RuntimeError(f"No '! total energy' line in si_ecut{ecut}.out")
    energies.append(float(m[-1]))

# 1 meV/atom criterion: converged at the smallest ecut_i (i>=1) with
# |E_i - E_{i-1}| / nat < 1 meV/atom (1 meV = 1e-3/13.605693122 Ry)
MEV_IN_RY = 1e-3 / 13.605693122
nat = 2
converged = None
for i in range(1, len(grid)):
    delta_per_atom_ry = abs(energies[i] - energies[i - 1]) / nat
    if delta_per_atom_ry < 1.0 * MEV_IN_RY:
        converged = grid[i]
        break
if converged is None:
    raise RuntimeError("Not converged even at 60 Ry")

results = {
    "values": {
        "ecutwfc_grid": grid,
        "total_energies": energies,
        "converged_ecutwfc": converged,
        "criterion_meV_per_atom": 1.0,
    },
    "units": {
        "ecutwfc_grid": "Ry",
        "total_energies": "Ry",
        "converged_ecutwfc": "Ry",
        "criterion_meV_per_atom": "meV/atom",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("energies:", energies)
print("converged_ecutwfc:", converged)
PYEOF

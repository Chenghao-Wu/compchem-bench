#!/usr/bin/env bash
# Oracle solution: geometry optimization of H2O with the pinned ASE
# LennardJones calculator. Demonstrates real execution — no hardcoded answers.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase import Atoms
from ase.calculators.lj import LennardJones
from ase.optimize import BFGS

# Build H2O with approximate geometry (O at origin, H at ~0.96 Å, ~104.5° angle)
d = 0.96  # O-H bond length in Å
theta = np.radians(104.5 / 2)
positions = [
    [0.0,             0.0,  0.0],           # O
    [d * np.sin(theta),  0.0,  d * np.cos(theta)],  # H1
    [-d * np.sin(theta), 0.0,  d * np.cos(theta)],  # H2
]

mol = Atoms("OH2", positions=positions)

# Pinned calculator (must match instruction.md and tests/verify.py exactly)
mol.calc = LennardJones(epsilon=0.01, sigma=1.0, rc=5.0)

opt = BFGS(mol, trajectory="opt.traj", logfile="opt.log")
opt.run(fmax=0.05)

final_energy = float(mol.get_potential_energy())
forces = mol.get_forces()
max_force = float(np.max(np.linalg.norm(forces, axis=1)))
oh_bond = float(np.linalg.norm(mol.positions[1] - mol.positions[0]))

results = {
    "values": {
        "final_energy": final_energy,
        "max_force": max_force,
        "n_steps": int(opt.get_number_of_steps()),
        "oh_bond_length": oh_bond,
    },
    "units": {
        "final_energy": "eV",
        "max_force": "eV/Å",
        "n_steps": "1",
        "oh_bond_length": "Å",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Optimization complete: E={final_energy:.6f} eV, fmax={max_force:.6f} eV/Å")
print(f"O-H bond length: {oh_bond:.4f} Å, steps={opt.get_number_of_steps()}")
PYEOF

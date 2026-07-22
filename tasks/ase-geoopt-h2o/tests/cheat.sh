#!/usr/bin/env bash
# Informed cheat: models a forger who knows ASE and the task, but does NOT
# run the optimization. Builds a plausible opt.traj whose frames carry
# fabricated SinglePointCalculator results (descending energies, zero
# forces) and a results.json whose energy is the TRUE pinned-calculator
# energy of the final geometry (so even an energy-only recompute would
# pass) — but with forces claimed as zero.
#
# Must FAIL: the verifier recomputes energy AND forces from the final
# geometry with the pinned LennardJones calculator; the real forces of this
# un-optimized geometry are far above the 0.05 eV/Å threshold.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase import Atoms
from ase.calculators.lj import LennardJones
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io import write

# Plausible H2O geometry (near-equilibrium for real water, NOT minimized
# under the pinned LJ potential)
d = 0.96
theta = np.radians(104.5 / 2)
positions = [
    [0.0, 0.0, 0.0],
    [d * np.sin(theta), 0.0, d * np.cos(theta)],
    [-d * np.sin(theta), 0.0, d * np.cos(theta)],
]

frames = []
for i, e in enumerate([-0.0040, -0.0035, -0.003257]):
    mol = Atoms("OH2", positions=positions)
    # Fabricated results: descending energies, zero forces
    mol.calc = SinglePointCalculator(mol, energy=e, forces=np.zeros((3, 3)))
    frames.append(mol)

write("opt.traj", frames)

# The forger even computes the TRUE LJ energy of the geometry so that an
# energy-only cross-check would pass:
mol_true = Atoms("OH2", positions=positions)
mol_true.calc = LennardJones(epsilon=0.01, sigma=1.0, rc=5.0)
true_e = float(mol_true.get_potential_energy())

results = {
    "values": {
        "final_energy": true_e,
        "max_force": 0.001,
        "n_steps": 8,
        "oh_bond_length": float(np.linalg.norm(positions[1])),
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

print(f"Forged trajectory + results.json written (claimed E={true_e:.6f} eV, fmax=0.001)")
PYEOF

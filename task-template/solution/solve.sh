#!/usr/bin/env bash
# Oracle solution: <one-line description of what the agent must achieve>.
#
# Requirements:
#   * Real execution — run the actual software; NEVER hardcode reference values.
#   * Must exit 0 and produce every output verify.py expects (CI runs it 3× and
#     requires the verifier to pass 3/3 AND solve.sh itself to exit 0).
#   * This file never enters the image (the CI runner mounts /solution), so it
#     may read anything under the task dir, but at runtime only /workspace and
#     the image contents are available.
set -euo pipefail
cd /workspace

# TODO(author): implement the oracle. Example skeleton (ASE):
#
#   python3 << 'PYEOF'
#   import json
#   import numpy as np
#   from ase import Atoms
#   from ase.calculators.lj import LennardJones
#   from ase.optimize import BFGS
#
#   d = 0.96
#   theta = np.radians(104.5 / 2)
#   positions = [
#       [0.0, 0.0, 0.0],
#       [d * np.sin(theta), 0.0, d * np.cos(theta)],
#       [-d * np.sin(theta), 0.0, d * np.cos(theta)],
#   ]
#   mol = Atoms("OH2", positions=positions)
#   mol.calc = LennardJones(epsilon=0.01, sigma=1.0, rc=5.0)
#   opt = BFGS(mol, trajectory="opt.traj")
#   opt.run(fmax=0.05)
#
#   results = {
#       "values": {
#           "final_energy": float(mol.get_potential_energy()),
#           "max_force": float(np.max(np.linalg.norm(mol.get_forces(), axis=1))),
#       },
#       "units": {"final_energy": "eV", "max_force": "eV/Å"},
#   }
#   with open("results.json", "w") as f:
#       json.dump(results, f, indent=2)
#   PYEOF

echo "TODO(author): implement solve.sh"
exit 1

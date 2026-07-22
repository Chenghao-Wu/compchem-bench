#!/usr/bin/env bash
# Oracle solution: correct MorseCalculator (analytic energy AND forces),
# then a real BFGS relaxation of the start cluster. No hardcoded answers.
set -euo pipefail
cd /workspace

cat > morse_calculator.py << 'PYEOF'
import numpy as np
from ase.calculators.calculator import Calculator, all_changes


class MorseCalculator(Calculator):
    """Pair Morse potential: V(r) = D_e*((1-exp(-a*(r-r_e)))^2 - 1)."""

    implemented_properties = ["energy", "forces"]

    D_e = 0.5   # eV
    a = 1.5     # 1/Å
    r_e = 2.5   # Å

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def calculate(self, atoms=None, properties=("energy", "forces"),
                  system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        pos = self.atoms.get_positions()
        n = len(pos)
        energy = 0.0
        forces = np.zeros((n, 3))
        for i in range(n):
            for j in range(i + 1, n):
                rv = pos[i] - pos[j]
                r = np.linalg.norm(rv)
                x = np.exp(-self.a * (r - self.r_e))
                energy += self.D_e * ((1.0 - x) ** 2 - 1.0)
                dvdR = 2.0 * self.D_e * self.a * (1.0 - x) * x
                f = -dvdR * rv / r  # force on atom i
                forces[i] += f
                forces[j] -= f
        self.results["energy"] = energy
        self.results["forces"] = forces
PYEOF

python3 << 'PYEOF'
import json
import numpy as np
from ase.io import read, write
from ase.optimize import BFGS
from morse_calculator import MorseCalculator

atoms = read("/workspace/assets/start.xyz")
atoms.calc = MorseCalculator()
opt = BFGS(atoms, logfile=None)
opt.run(fmax=0.05)

write("relaxed.xyz", atoms, format="extxyz")

energy = float(atoms.get_potential_energy())
fmax = float(np.max(np.linalg.norm(atoms.get_forces(), axis=1)))

results = {
    "values": {"final_energy": energy, "max_force": fmax,
               "n_steps": int(opt.get_number_of_steps())},
    "units": {"final_energy": "eV", "max_force": "eV/Å", "n_steps": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Relaxed: E={energy:.8f} eV, fmax={fmax:.6f}, steps={opt.get_number_of_steps()}")
PYEOF

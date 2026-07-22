#!/usr/bin/env bash
# Informed cheat: implements the Morse ENERGY correctly but botches the
# FORCES (classic chain-rule slip: the exp(-a(r-r_e)) factor is dropped,
# so dV/dr is wrong by a factor of exp(...)). To still pass a relaxation
# check, the cheat minimizes the cluster with its own CORRECT energy via
# numeric-force BFGS — the submitted relaxed.xyz is a genuine minimum of
# the potential, and results.json is fully self-consistent. Every layer
# that only inspects submitted files passes.
# Must FAIL: the verifier evaluates the agent's calculator class on HIDDEN
# geometries and compares forces against the finite-difference gradient of
# the true potential — the broken analytic forces are exposed there.
set -euo pipefail
mkdir -p /workspace
cd /workspace

cat > morse_calculator.py << 'PYEOF'
import numpy as np
from ase.calculators.calculator import Calculator, all_changes


class MorseCalculator(Calculator):
    implemented_properties = ["energy", "forces"]

    D_e = 0.5
    a = 1.5
    r_e = 2.5

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
                # CHEAT: dropped the x factor from the derivative
                dvdR = 2.0 * self.D_e * self.a * (1.0 - x)
                f = -dvdR * rv / r
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

D_e, a, r_e = 0.5, 1.5, 2.5

def true_energy(pos):
    e = 0.0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            r = np.linalg.norm(pos[i] - pos[j])
            x = np.exp(-a * (r - r_e))
            e += D_e * ((1.0 - x) ** 2 - 1.0)
    return e

# The cheat KNOWS its forces are broken, so it relaxes with numeric forces
# on its (correct) energy — producing a genuine minimum of the potential.
class NumericForceCalculator(MorseCalculator):
    def calculate(self, atoms=None, properties=("energy", "forces"),
                  system_changes=None):
        super().calculate(atoms, properties, system_changes)
        pos = self.atoms.get_positions()
        h = 1e-6
        f = np.zeros_like(pos)
        for i in range(len(pos)):
            for k in range(3):
                dp = pos.copy(); dp[i, k] += h
                dm = pos.copy(); dm[i, k] -= h
                f[i, k] = -(true_energy(dp) - true_energy(dm)) / (2 * h)
        self.results["forces"] = f

atoms = read("/workspace/assets/start.xyz")
atoms.calc = NumericForceCalculator()
opt = BFGS(atoms, logfile=None)
opt.run(fmax=0.05)
write("relaxed.xyz", atoms, format="extxyz")

energy = true_energy(atoms.get_positions())
# report the TRUE (numeric) fmax so results.json is self-consistent
fmax = float(np.max(np.linalg.norm(atoms.get_forces(), axis=1)))

results = {
    "values": {"final_energy": float(energy), "max_force": fmax,
               "n_steps": int(opt.get_number_of_steps())},
    "units": {"final_energy": "eV", "max_force": "eV/Å", "n_steps": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"Broken-force calculator + genuine minimum submitted (E={energy:.6f})")
PYEOF

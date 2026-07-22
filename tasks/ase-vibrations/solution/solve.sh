#!/usr/bin/env bash
# Oracle solution: EMT optimization of tetrahedral Cu4 + Vibrations run.
# Real execution, no hardcoded answers.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
from ase.optimize import BFGS
from ase.vibrations import Vibrations

# Slightly perturbed tetrahedron (deterministic seed) as starting guess
base = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], float)
base *= 2.6 / (2 * np.sqrt(2))
rng = np.random.RandomState(42)
pos = base + rng.uniform(-0.15, 0.15, base.shape)

atoms = Atoms("Cu4", positions=pos)
atoms.calc = EMT()
opt = BFGS(atoms, logfile=None)
opt.run(fmax=0.01)

write("optimized.xyz", atoms, format="extxyz")

vib = Vibrations(atoms, name="vib")
vib.run()
freqs = vib.get_frequencies()
vib_freqs = sorted(float(np.real(f)) for f in freqs[-6:])
n_imag = int(sum(1 for f in freqs if abs(np.imag(f)) > 10.0))

results = {
    "values": {
        "n_modes": int(len(freqs)),
        "n_imaginary": n_imag,
        **{f"freq_{i+1}": vib_freqs[i] for i in range(6)},
    },
    "units": {
        "n_modes": "1",
        "n_imaginary": "1",
        **{f"freq_{i+1}": "cm^-1" for i in range(6)},
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("vibrational frequencies (cm^-1):", [f"{v:.3f}" for v in vib_freqs])
print("n_imaginary:", n_imag)
PYEOF

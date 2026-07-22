#!/usr/bin/env bash
# Informed cheat #2 ("genuine cache, fabricated numbers"): runs the FULL
# pipeline correctly (real optimization, real Vibrations, genuine cache) —
# then reports frequencies scaled by 1.15 in results.json, betting the
# verifier only checks file existence or trusts results.json.
# Must FAIL: the verifier reloads the vib/ cache and compares it against
# results.json (cache-consistency layer), independent of the L4 rerun.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
from ase.optimize import BFGS
from ase.vibrations import Vibrations

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
true_freqs = sorted(float(np.real(f)) for f in freqs[-6:])

# Fabricated report: everything genuine except the numbers in results.json
fake_freqs = [f * 1.15 for f in true_freqs]
results = {
    "values": {
        "n_modes": 12,
        "n_imaginary": 0,
        **{f"freq_{i+1}": fake_freqs[i] for i in range(6)},
    },
    "units": {
        "n_modes": "1",
        "n_imaginary": "1",
        **{f"freq_{i+1}": "cm^-1" for i in range(6)},
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Genuine cache + fabricated results.json submitted")
PYEOF

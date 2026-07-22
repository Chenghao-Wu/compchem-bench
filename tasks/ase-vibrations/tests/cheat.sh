#!/usr/bin/env bash
# Informed cheat #1 ("honest wrong-geometry"): runs a REAL Vibrations
# analysis — but on the UNOPTIMIZED starting cluster, and submits that as
# optimized.xyz together with the truthful frequencies of the
# non-stationary geometry (including its imaginary modes, hidden by
# reporting n_imaginary=0 and only real parts).
# Must FAIL: the verifier recomputes EMT forces on optimized.xyz (far above
# threshold) — a vibrational analysis of a non-minimum is rejected no
# matter how honestly the numbers are reported.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
from ase.vibrations import Vibrations

base = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], float)
base *= 2.6 / (2 * np.sqrt(2))
rng = np.random.RandomState(42)
pos = base + rng.uniform(-0.15, 0.15, base.shape)

atoms = Atoms("Cu4", positions=pos)  # NOT optimized — this is the cheat
atoms.calc = EMT()
write("optimized.xyz", atoms, format="extxyz")

vib = Vibrations(atoms, name="vib")
vib.run()
freqs = vib.get_frequencies()
vib_freqs = sorted(float(np.real(f)) for f in freqs[-6:])

results = {
    "values": {
        "n_modes": 12,
        "n_imaginary": 0,  # lie about the imaginary modes
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
print("Honest-but-unoptimized vibrations submitted")
PYEOF

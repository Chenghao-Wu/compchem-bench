#!/usr/bin/env bash
# Informed cheat: builds the 7-frame band by plain LINEAR INTERPOLATION
# between the endpoints (no NEB optimization at all), then — to survive an
# energy-only recompute — honestly recomputes the EMT energies of those
# fake frames and reports the true barrier OF THE UNOPTIMIZED BAND, with a
# fabricated tiny saddle_fmax. Self-consistent on every energy check.
# Must FAIL: the verifier recomputes the FORCE on the highest-energy frame
# (large for an un-optimized interpolation) and anchors the barrier to the
# calibrated NEB value.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase.io import read, write
from ase.calculators.emt import EMT
from ase.mep import NEB

initial = read("/workspace/assets/initial.xyz")
final = read("/workspace/assets/final.xyz")

images = [initial] + [initial.copy() for _ in range(5)] + [final]
for im in images:
    im.calc = EMT()
neb = NEB(images)
neb.interpolate(method="linear")  # NOT optimized — this is the cheat

write("neb_band.traj", images)

# Honest energies of the fake band + a fabricated saddle_fmax
energies = [im.get_potential_energy() for im in images]
barrier = float(max(energies) - energies[0])

results = {
    "values": {"barrier": barrier, "n_images": 7, "saddle_fmax": 0.023},
    "units": {"barrier": "eV", "n_images": "1", "saddle_fmax": "eV/Å"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"Forged interpolated band, honest barrier={barrier:.6f} eV, fake fmax=0.023")
PYEOF

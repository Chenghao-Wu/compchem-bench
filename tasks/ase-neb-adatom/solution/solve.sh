#!/usr/bin/env bash
# Oracle solution: NEB (climbing image, IDPP start) for the adatom hop,
# band written to neb_band.traj. Real execution, no hardcoded answers.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase.io import read, write
from ase.calculators.emt import EMT
from ase.mep import NEB
from ase.optimize import MDMin

initial = read("/workspace/assets/initial.xyz")
final = read("/workspace/assets/final.xyz")

n_images = 7
images = [initial] + [initial.copy() for _ in range(n_images - 2)] + [final]
for im in images:
    im.calc = EMT()

neb = NEB(images, climb=True)
neb.interpolate(method="idpp")
opt = MDMin(neb, logfile=None)
opt.run(fmax=0.05, steps=2000)

write("neb_band.traj", images)

energies = [im.get_potential_energy() for im in images]
barrier = float(max(energies) - energies[0])
imax = int(np.argmax(energies))
saddle_fmax = float(np.max(np.linalg.norm(images[imax].get_forces(), axis=1)))

results = {
    "values": {"barrier": barrier, "n_images": n_images, "saddle_fmax": saddle_fmax},
    "units": {"barrier": "eV", "n_images": "1", "saddle_fmax": "eV/Å"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"NEB converged: barrier={barrier:.6f} eV, saddle fmax={saddle_fmax:.4f} eV/Å")
PYEOF

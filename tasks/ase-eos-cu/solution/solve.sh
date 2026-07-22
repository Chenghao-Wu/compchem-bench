#!/usr/bin/env bash
# Oracle solution: EOS for FCC Cu using ASE EMT.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np
from ase.build import bulk
from ase.calculators.emt import EMT
from ase.eos import EquationOfState

a_values = np.linspace(3.5, 3.7, 7)
volumes = []
energies = []

rows = []
for a in a_values:
    cu = bulk("Cu", "fcc", a=float(a))
    cu.calc = EMT()
    e = cu.get_potential_energy()
    v = cu.get_volume()
    volumes.append(v)
    energies.append(e)
    rows.append(f"{a:.6f},{v:.6f},{e:.6f}")

with open("eos_data.csv", "w") as f:
    f.write("\n".join(rows) + "\n")

eos = EquationOfState(volumes, energies, eos="birchmurnaghan")
v0, e0, b0_eV_per_A3 = eos.fit()
b0_GPa = b0_eV_per_A3 * 160.21766  # eV/Å³ → GPa

results = {
    "values": {
        "V0": float(v0),
        "E0": float(e0),
        "B0": float(b0_GPa),
        "n_points": 7,
    },
    "units": {
        "V0": "Å³",
        "E0": "eV",
        "B0": "GPa",
        "n_points": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"V0={v0:.4f} Å³  E0={e0:.6f} eV  B0={b0_GPa:.1f} GPa")
PYEOF

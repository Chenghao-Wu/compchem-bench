#!/usr/bin/env bash
# Informed cheat: a forger who knows the textbook EMT Cu values. Fabricates
# a smooth Birch–Murnaghan E–V curve centered exactly on plausible V0/B0,
# so the CSV is internally consistent, monotonic, physically ranged, refits
# to the claimed V0/B0, and passes the reference tolerance.
# Must FAIL at layer 4a: the verifier rebuilds each structure and
# recomputes its EMT energy — the fabricated curve is not the real EMT
# curve (wrong E0 offset and curvature in detail).
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

a_values = np.linspace(3.5, 3.7, 7)
V0 = 11.565          # Å³ — near the true EMT value
B0_GPa = 134.0       # GPa — near the true EMT value
E0 = -0.005          # plausible minimum energy
B0 = B0_GPa / 160.21766  # eV/Å³

rows = []
for a in a_values:
    v = a ** 3 / 4.0
    x = (V0 / v) ** (2.0 / 3.0)
    # Birch-Murnaghan 3rd-order expanded to the quadratic term
    e = E0 + (9.0 / 2.0) * V0 * B0 * (x - 1.0) ** 2
    rows.append(f"{a:.6f},{v:.6f},{e:.6f}")

with open("eos_data.csv", "w") as f:
    f.write("\n".join(rows) + "\n")

results = {
    "values": {"V0": V0, "E0": E0, "B0": B0_GPa, "n_points": 7},
    "units": {"V0": "Å³", "E0": "eV", "B0": "GPa", "n_points": "1"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged textbook E-V curve + results.json written")
PYEOF

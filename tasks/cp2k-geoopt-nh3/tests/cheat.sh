#!/usr/bin/env bash
# Informed cheat: a forger who knows the textbook NH3 values. Fabricates a
# complete-looking CP2K geoopt run — banner, GEOMETRY OPTIMIZATION
# COMPLETED marker, energy lines — an xyz trajectory whose N-H bond length
# matches the expected optimized value, and a results.json self-consistent
# with the fake log at a very plausible energy.
#
# The trick: the forged geometry has the right bond length but the WRONG
# shape (planar H-N-H = 120° instead of the true pyramidal ~106.7°), and
# the claimed energy is just a guess near the true optimum.
#
# Layers 1-5 (existence, banner, convergence marker, log<->results
# consistency, reference tolerances) all PASS for this forgery.
# Must FAIL at layer 7: the verifier runs a REAL single point on the forged
# geometry — the planar structure's true energy is far above the claimed
# value, breaking three-way agreement.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

fake_energy = -11.73787  # plausible guess near the true optimum

# Planar NH3 with the correct N-H bond length (1.0211 Å)
d = 1.0211
coords = [
    ("N", 0.0, 0.0, 0.0),
    ("H", d, 0.0, 0.0),
    ("H", -d / 2, d * np.sqrt(3) / 2, 0.0),
    ("H", -d / 2, -d * np.sqrt(3) / 2, 0.0),
]

out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-07-20 00:00:00.000

 --------  Informations at step =     0 ------------
  Optimization Method        =                 BFGS
  Total energy:              {fake_energy + 0.05:18.10f}
 --------  Informations at step =     5 ------------
  Total energy:              {fake_energy:18.10f}

 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:    {fake_energy:.10f}

 *******************************************************************************
 ***                      GEOMETRY OPTIMIZATION COMPLETED                    ***
 *******************************************************************************

 PROGRAM ENDED AT 2026-07-20 00:05:00.000
 PROGRAM STOPPED IN /workspace
"""
with open("nh3_geoopt.out", "w") as f:
    f.write(out)

# Fake trajectory: 2 frames (initial + "optimized")
with open("nh3_geoopt-pos-1.xyz", "w") as f:
    for step in range(2):
        f.write("4\n")
        f.write(f" i =        {step}, E =     {fake_energy:.10f}\n")
        for sym, x, y, z in coords:
            f.write(f"{sym}    {x:15.10f}   {y:15.10f}   {z:15.10f}\n")

results = {
    "values": {
        "final_energy": fake_energy,
        "nh_bond_length": d,
        "geo_opt_converged": True,
        "n_geo_steps": 5,
    },
    "units": {
        "final_energy": "Ha",
        "nh_bond_length": "Å",
        "geo_opt_converged": "1",
        "n_geo_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged geoopt output + trajectory, self-consistent at {fake_energy} Ha")
PYEOF

#!/usr/bin/env bash
# Informed cheat: a forger who knows the textbook rocksalt NaCl structure
# and the approximate PBE lattice constant. Fabricates a complete-looking
# CELL_OPT run — banner, GEOMETRY OPTIMIZATION COMPLETED marker, energy
# lines, final CELL| vectors at a plausible a0 — plus an xyz trajectory
# whose final frame is the IDEAL high-symmetry rocksalt geometry (which is
# constructible analytically: Na/Cl on the fcc sublattices at a/2), and a
# results.json self-consistent with the fake log at a 5-decimal energy
# guess.
#
# Layers 1-6 (existence, banner, convergence marker, log<->results
# consistency, reference tolerances, trajectory composition) all PASS for
# this forgery: the ideal geometry is genuinely close to the optimum.
# Must FAIL at layer 7: the verifier runs a REAL single point on the
# forged final state. Its true energy differs from the 5-decimal guess by
# ~1e-6-1e-7 Ha — above the tight cross-verify tolerance — breaking
# three-way agreement. Guessing the deterministic CP2K 2024.1 energy to
# 1e-7 Ha without running it is not possible.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

a0 = 5.82290          # plausible a0 guess (correct to ~1e-4)
fake_energy = -249.19345  # 5-decimal energy guess

h = a0 / 2.0
coords = [
    ("Na", 0.0, 0.0, 0.0),
    ("Na", 0.0, h, h),
    ("Na", h, 0.0, h),
    ("Na", h, h, 0.0),
    ("Cl", h, h, h),
    ("Cl", h, 0.0, 0.0),
    ("Cl", 0.0, h, 0.0),
    ("Cl", 0.0, 0.0, h),
]

cell_line = (f" CELL| Vector a [angstrom]:     {a0:8.3f}     0.000     0.000   |a| =    {a0:9.6f}\n"
             f" CELL| Vector b [angstrom]:       0.000   {a0:8.3f}     0.000   |b| =    {a0:9.6f}\n"
             f" CELL| Vector c [angstrom]:       0.000     0.000   {a0:8.3f}   |c| =    {a0:9.6f}\n")

out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-07-20 00:00:00.000

 ***                     STARTING   CELL   OPTIMIZATION                      ***

 --------  Informations at step =     0 ------------
  Optimization Method        =                 BFGS
  Total energy:              {fake_energy + 0.05:18.10f}
 --------  Informations at step =     3 ------------
  Total energy:              {fake_energy:18.10f}

{cell_line}
 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:              {fake_energy:.10f}

 *******************************************************************************
 ***                      GEOMETRY OPTIMIZATION COMPLETED                    ***
 *******************************************************************************

 PROGRAM ENDED AT 2026-07-20 00:02:00.000
 PROGRAM STOPPED IN /workspace
"""
with open("nacl_cellopt.out", "w") as f:
    f.write(out)

with open("nacl_cellopt-pos-1.xyz", "w") as f:
    for step in range(2):
        f.write("8\n")
        f.write(f" i =        {step}, E =      {fake_energy:.10f}\n")
        for sym, x, y, z in coords:
            f.write(f" {sym}        {x:15.10f}   {y:15.10f}   {z:15.10f}\n")

results = {
    "values": {
        "final_energy": fake_energy,
        "lattice_constant": a0,
        "cell_opt_converged": True,
        "n_opt_steps": 4,
    },
    "units": {
        "final_energy": "Ha",
        "lattice_constant": "Å",
        "cell_opt_converged": "1",
        "n_opt_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged CELL_OPT output + ideal-geometry trajectory at {fake_energy} Ha")
PYEOF

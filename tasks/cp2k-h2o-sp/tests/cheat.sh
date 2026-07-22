#!/usr/bin/env bash
# Informed cheat: fabricate a complete-looking CP2K output — banner, SCF
# iteration table, ENERGY| line, PROGRAM ENDED AT marker — self-consistent
# with results.json, using a guessed energy (no actual CP2K run).
# Must FAIL: the guessed energy is outside the 1e-5 Ha reference tolerance,
# and the verifier's own recompute of the identical input will not match.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

fake_energy = -17.20418  # plausible-looking guess for H2O PBE/DZVP

scf_table = "\n".join(
    f"  {i:3d}     {fake_energy + 0.5 - i*0.01:18.10f}   {1e-3/i:12.6e}   {1e-4/i:12.6e}"
    for i in range(1, 9)
)

out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-07-20 00:00:00.000

 SCF WAVEFUNCTION OPTIMIZATION
 Step     Update method      Time    Convergence         Total energy    Change
{scf_table}

 *** SCF run converged in     8 steps ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:    {fake_energy:.10f}

 PROGRAM ENDED AT 2026-07-20 00:01:00.000
 PROGRAM STOPPED IN /workspace
"""
with open("h2o_sp.out", "w") as f:
    f.write(out)

results = {
    "values": {
        "total_energy": fake_energy,
        "scf_converged": True,
        "n_scf_steps": 8,
    },
    "units": {
        "total_energy": "Ha",
        "scf_converged": "1",
        "n_scf_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged CP2K output with self-consistent guessed energy {fake_energy} Ha")
PYEOF

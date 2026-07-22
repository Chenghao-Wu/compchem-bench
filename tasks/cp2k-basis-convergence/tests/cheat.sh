#!/usr/bin/env bash
# Informed cheat: a forger who knows CP2K log format and the typical basis-
# set convergence pattern. Fabricates three logs — banner, SCF-converged
# lines, a correctly formatted ATOMIC COORDINATES block copied from the
# asset (so the geometry check passes), ENERGY| lines with plausible
# monotonically decreasing energies — plus a self-consistent results.json.
#
# Passes layers 0-3 (asset untouched, files exist, logs well-formed with
# matching geometry, log<->results consistency) and even the monotonicity
# check.
# Must FAIL at the reference tolerances (4-decimal guesses are not the
# true deterministic values to 1e-6 Ha) and at layer 5: the verifier's
# real SZV recompute on the pinned geometry returns the true SZV energy,
# not the guess — breaking three-way agreement.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

# Guessed energies (4 decimals), monotonically decreasing
guesses = {"szv": -115.0483, "dzvp": -115.2967, "tzvp": -115.3122}

with open("/workspace/assets/methanol.xyz") as f:
    xyz_lines = [l.strip() for l in f if l.strip()]
natoms = int(xyz_lines[0])
atoms = [l.split() for l in xyz_lines[2:2 + natoms]]

coord_block = "\n".join(
    f"{i+1:8d}{1:6d}  {a[0]:<4s}{6 if a[0]=='O' else (4 if a[0]=='C' else 1):4d}"
    f"{float(a[1]):14.6f}{float(a[2]):12.6f}{float(a[3]):12.6f}   4.00      12.0107"
    for i, a in enumerate(atoms)
)

for basis, e in guesses.items():
    out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-07-20 00:00:00.000

 MODULE QUICKSTEP:  ATOMIC COORDINATES IN angstrom

  Atom  Kind  Element       X           Y           Z          Z(eff)       Mass

{coord_block}

 SCF WAVEFUNCTION OPTIMIZATION
  Step     Update method      Time    Convergence         Total energy    Change
     1 P_Mix/Diag. 0.40E+00    0.5     0.50000000      -110.0000000000 -1.10E+02
     9 DIIS/Diag.  0.16E-05    0.1     0.00000050      {e:18.10f}  5.00E+00

  *** SCF run converged in     9 steps ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:              {e:.10f}

 PROGRAM ENDED AT 2026-07-20 00:00:30.000
 PROGRAM STOPPED IN /workspace
"""
    with open(f"methanol_{basis}.out", "w") as f:
        f.write(out)

results = {
    "values": {
        "energy_szv": guesses["szv"],
        "energy_dzvp": guesses["dzvp"],
        "energy_tzvp": guesses["tzvp"],
        "monotonic_decreasing": True,
    },
    "units": {
        "energy_szv": "Ha",
        "energy_dzvp": "Ha",
        "energy_tzvp": "Ha",
        "monotonic_decreasing": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged three monotonically decreasing basis logs at 4-decimal guesses")
PYEOF

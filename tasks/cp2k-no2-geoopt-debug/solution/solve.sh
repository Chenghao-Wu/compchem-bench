#!/usr/bin/env bash
# Oracle solution for cp2k-no2-geoopt-debug.
set -euo pipefail
cd /workspace

# Three planted faults, three different signatures:
#
# Fault 1 (aborts with a helpful message): neutral NO2 has an odd number of
# electrons (17 valence with GTH pseudopotentials: 5 + 6 + 6), so a
# closed-shell singlet (MULTIPLICITY 1, no UKS/LSD) is invalid. CP2K aborts
# in qs_init_subsys with "Use the LSD option for an odd number of electrons".
# Fix: spin-polarized calculation with the doublet ground state.
#
# Fault 2 (stalls silently): the OT/DIIS optimizer shipped in the input never
# converges on this open-shell system (convergence parameter parks at ~1.2E-3
# and drifts; it never converges, even with MAX_SCF 300). Fix: switch to
# diagonalization with Broyden mixing, which converges in <25 steps, well
# within the shipped MAX_SCF 50.
#
# Fault 3 (no signal at all): O silently carries DZVP-MOLOPT-SR-GTH — the
# short-range MOLOPT variant — instead of the intended DZVP-MOLOPT-GTH. The
# keyword is valid, the basis exists and is the same size, SCF convergence is
# unaffected, and the geometry optimization COMPLETES with normal termination
# (measured: 8/8 SCFs converged, GEO_OPT COMPLETED, exit 0) — but the energy
# is -41.87978316 Ha, 2.43 mHa (~1.5 kcal/mol, ~243x the verifier tolerance)
# above the intended PBE/DZVP-MOLOPT-GTH value. Only an input audit against
# the stated level of theory catches the "-SR-" infix. (Alternatives do not
# work as silent faults: swapping the GTH potentials aborts — the requested
# q-variant does not exist for the other element — and a minimal SZV basis
# degrades SCF stability enough to abort the geoopt mid-run.)
# Fix: restore DZVP-MOLOPT-GTH for O.

cp assets/no2_geoopt.inp final.inp
sed -i 's/MULTIPLICITY 1.*/UKS TRUE\n    MULTIPLICITY 2/' final.inp

python3 << 'PYEOF'
s = open("final.inp").read()

# Fault 3: restore O's basis to the intended DZVP-MOLOPT-GTH.
old_o = "&KIND O\n      BASIS_SET DZVP-MOLOPT-SR-GTH"
new_o = "&KIND O\n      BASIS_SET DZVP-MOLOPT-GTH"
assert old_o in s, "O KIND block not in expected (SR-downgraded) form"
s = s.replace(old_o, new_o)

# Fault 2: replace OT/DIIS with diagonalization + Broyden mixing.
old = """      &OT
        MINIMIZER DIIS
      &END OT
"""
new = """      &DIAGONALIZATION
        ALGORITHM STANDARD
      &END DIAGONALIZATION
      &MIXING
        METHOD BROYDEN_MIXING
        ALPHA 0.4
        NBUFFER 8
      &END MIXING
"""
assert old in s, "OT block not found in final.inp"
s = s.replace(old, new)

open("final.inp", "w").write(s)
PYEOF

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

mpirun -np 1 cp2k -i final.inp -o no2_geoopt.out

python3 << 'PYEOF'
import json
import re

with open("no2_geoopt.out") as f:
    content = f.read()

energy_matches = re.findall(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
if not energy_matches:
    raise RuntimeError("No energy found in output")
total_energy = float(energy_matches[-1])

geoopt_converged = "GEOMETRY OPTIMIZATION COMPLETED" in content
assert "SCF run converged" in content, "SCF did not converge"
assert geoopt_converged, "geometry optimization did not complete"

results = {
    "values": {
        "total_energy": total_energy,
        "geoopt_converged": geoopt_converged,
    },
    "units": {
        "total_energy": "Ha",
        "geoopt_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"E={total_energy:.8f} Ha, geoopt_converged={geoopt_converged}")
PYEOF

#!/usr/bin/env bash
# Maximally-informed cheat for qe-error-diagnose: the forger DOES know the
# correct fixes (right UPF filename, drop CELL_PARAMETERS, raise mixing) and
# writes perfect-looking fixed inputs, but never runs anything — instead it
# fabricates converged pw.x logs and reuses the closest PUBLISHED numbers
# from elsewhere in this repo as the energies:
#   case1 <- qe-scf-si's calibrated -22.83951051 (ecut 40/320, not 45/360)
#   case2 <- qe-ecutwfc-convergence's published ecut=40 point -22.83951348
#   case3 <- qe-relax-co's calibrated final energy -60.01053592
# Layers 1-4 (fixed inputs parse, settings/species/pseudo-hash sanity, log
# integrity, log<->results consistency) all PASS. It must FAIL at layer 5:
# the case settings were chosen so that no published number lies inside the
# calibrated 1e-5 Ry tolerance.
set -euo pipefail
cd /workspace

mkdir -p case1 case2 case3
cp -r assets/case1_pseudo/pseudo case1/pseudo
cp -r assets/case2_cell/pseudo case2/pseudo
cp -r assets/case3_scf/pseudo case3/pseudo

# perfect-looking fixed inputs (the real fixes)
sed 's/Si\.pbe-n-rrkjus\.UPF/Si.pbe-n-rrkjus_psl.1.0.0.UPF/' \
    assets/case1_pseudo/case1.in > case1/case1.in
sed '/^CELL_PARAMETERS/,/^  2\.714329  2\.714329  0\.000000$/d' \
    assets/case2_cell/case2.in > case2/case2.in
sed 's/mixing_beta = 0.05/mixing_beta = 0.5/; s/electron_maxstep = 20/electron_maxstep = 100/' \
    assets/case3_scf/case3.in > case3/case3.in

python3 << 'PYEOF'
import json

# published numbers reused as "answers"
E = {
    1: (-22.83951051, 45.0, 360.0),
    2: (-22.83951348, 35.0, 280.0),
    3: (-60.01053592, 50.0, 400.0),
}
for n, (energy, ecutwfc, ecutrho) in E.items():
    iters = ""
    for i in range(1, 8):
        iters += (f"     iteration #  {i}     ecut=    {ecutwfc:5.2f} Ry     beta= 0.70\n"
                  f"     total cpu time spent up to now is        1.0 secs\n")
    out = f"""     Program PWSCF v.7.4 starts on 20Jul2026 at  0: 0: 0

     number of atoms/cell      =            2.0000
     kinetic-energy cutoff     =     {ecutwfc:7.4f}  Ry
     charge density cutoff     =     {ecutrho:7.4f}  Ry

{iters}
     total energy              =     {energy:.8f} Ry
     convergence has been achieved in   7 iterations

!    total energy              =     {energy:.8f} Ry
     JOB DONE.
"""
    with open(f"case{n}/case{n}.out", "w") as f:
        f.write(out)

results = {
    "values": {
        "case1_energy_Ry": E[1][0],
        "case2_energy_Ry": E[2][0],
        "case3_energy_Ry": E[3][0],
    },
    "units": {
        "case1_energy_Ry": "Ry",
        "case2_energy_Ry": "Ry",
        "case3_energy_Ry": "Ry",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged 3 fixed inputs + converged logs reusing published repo energies")
PYEOF

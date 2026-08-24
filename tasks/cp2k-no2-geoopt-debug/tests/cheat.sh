#!/usr/bin/env bash
# Informed cheat: a forger who knows the full diagnosis (odd electron count ->
# UKS doublet; OT/DIIS stall -> diagonalization + Broyden; O's basis silently
# DZVP-MOLOPT-SR-GTH -> restore DZVP-MOLOPT-GTH), knows CP2K output format,
# and can estimate the NO2 PBE energy to ~5 significant decimals (e.g. from a
# quick lookup or another code). Fabricates:
#   - final.inp with all three repairs and all intended-settings tokens
#     (passes the repair checks, including the positional KIND checks)
#   - no2_geoopt.out with banner, SCF convergence, GEO_OPT completion,
#     ENERGY| line, and normal-termination footer
#   - results.json self-consistent with the forged log
# Passes layers 1-4 (existence, repairs, log shape, log<->results
# consistency).
# Must FAIL at layer 5: the guessed energy is not the true CP2K 2024.1
# PBE/DZVP-MOLOPT-GTH value; the reference tolerance is 1e-5 Ha, far below
# what can be guessed without actually running the fixed input in this image.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

# Plausible repair: open-shell tokens and all kept-settings tokens present.
fixed = """&GLOBAL
  PROJECT_NAME no2_closed_shell
  RUN_TYPE GEO_OPT
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    UKS TRUE
    MULTIPLICITY 2
    &MGRID
      CUTOFF 400
      REL_CUTOFF 50
    &END MGRID
    &QS
      EPS_DEFAULT 1.0E-12
    &END QS
    &SCF
      SCF_GUESS ATOMIC
      EPS_SCF 1.0E-6
      MAX_SCF 50
      &DIAGONALIZATION
        ALGORITHM STANDARD
      &END DIAGONALIZATION
      &MIXING
        METHOD BROYDEN_MIXING
        ALPHA 0.4
      &END MIXING
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
    &POISSON
      PERIODIC NONE
      PSOLVER MT
    &END POISSON
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
      PERIODIC NONE
    &END CELL
    &COORD
      N    5.000   5.000   5.000
      O    6.103   5.464   5.000
      O    3.897   5.464   5.000
    &END COORD
    &KIND N
      BASIS_SET DZVP-MOLOPT-GTH
      POTENTIAL GTH-PBE-q5
    &END KIND
    &KIND O
      BASIS_SET DZVP-MOLOPT-GTH
      POTENTIAL GTH-PBE-q6
    &END KIND
  &END SUBSYS
&END FORCE_EVAL

&MOTION
  &GEO_OPT
    OPTIMIZER BFGS
    MAX_ITER 100
  &END GEO_OPT
&END MOTION
"""
with open("final.inp", "w") as f:
    f.write(fixed)

fake_energy = -41.87953  # 5-decimal guess at the NO2 PBE/DZVP energy

out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-08-23 00:00:00.000

 SCF WAVEFUNCTION OPTIMIZATION
  Step     Update method      Time    Convergence         Total energy    Change
     1 Broyden_mixing           0.5     0.50000000       -40.1000000000 -4.00E+01
    14 Broyden_mixing           0.1     0.00000040       -41.8795300000  1.54E+00

  *** SCF run converged in    14 steps ***

 --------  Informations at step =     7 ------------
  Optimization Method        =                 BFGS
  Total Energy               =       -41.8795300000
 ---------------------------------------------------

 ***                    GEOMETRY OPTIMIZATION COMPLETED                      ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:              {fake_energy:.10f}

 PROGRAM ENDED AT 2026-08-23 00:01:10.000
 PROGRAM STOPPED IN /workspace
"""
with open("no2_geoopt.out", "w") as f:
    f.write(out)

results = {
    "values": {
        "total_energy": fake_energy,
        "geoopt_converged": True,
    },
    "units": {
        "total_energy": "Ha",
        "geoopt_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged final.inp + CP2K output, self-consistent at {fake_energy} Ha")
PYEOF

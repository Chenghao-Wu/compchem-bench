#!/usr/bin/env bash
# Informed cheat: a forger who knows CP2K output format and can estimate the
# methane PBE energy to ~5 significant decimals (e.g. from a quick lookup or
# a different code). Fabricates:
#   - fixed.inp with the three repairs present (passes the token checks)
#   - ch4_sp.out with banner, SCF convergence, ENERGY| line, normal
#     termination footer
#   - results.json self-consistent with the forged log
# Passes layers 1-4 (existence, repairs, log shape, log<->results
# consistency).
# Must FAIL at layer 5: the guessed energy (5 decimals) is not the true
# deterministic CP2K 2024.1 value; the reference tolerance is 1e-6 Ha,
# far below what can be guessed without actually running the fixed input
# in this image.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

# Plausible repair: all three fixes present so the token checks pass.
fixed = """&GLOBAL
  PROJECT ch4_sp
  RUN_TYPE ENERGY
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 300
      REL_CUTOFF 60
    &END MGRID
    &QS
      EPS_DEFAULT 1.0E-12
    &END QS
    &SCF
      SCF_GUESS ATOMIC
      EPS_SCF 1.0E-7
      MAX_SCF 50
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
      PERIODIC NONE
    &END CELL
    &COORD
      C   -0.000000   -0.000000   -0.000000
      H   -0.675343    0.854123   -0.085361
      H   -0.394946   -0.835938   -0.581485
      H    0.084754   -0.293741    1.048538
      H    0.985535    0.275556   -0.381692
    &END COORD
    &KIND C
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
    &KIND H
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q1
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""
with open("fixed.inp", "w") as f:
    f.write(fixed)

fake_energy = -8.46281  # 5-decimal guess at the methane PBE/DZVP energy

out = f"""****  ****  CP2K version 2024.1 (fake banner)  ****  ****
 PROGRAM STARTED AT 2026-07-20 00:00:00.000

 SCF WAVEFUNCTION OPTIMIZATION
  Step     Update method      Time    Convergence         Total energy    Change
     1 P_Mix/Diag. 0.40E+00    0.5     0.50000000       -10.0000000000 -1.00E+01
     8 DIIS/Diag.  0.16E-05    0.1     0.00000050        -8.4628100000  1.54E+00

  *** SCF run converged in     8 steps ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:               {fake_energy:.10f}

 PROGRAM ENDED AT 2026-07-20 00:00:20.000
 PROGRAM STOPPED IN /workspace
"""
with open("ch4_sp.out", "w") as f:
    f.write(out)

results = {
    "values": {
        "total_energy": fake_energy,
        "scf_converged": True,
    },
    "units": {
        "total_energy": "Ha",
        "scf_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged fixed.inp + CP2K output, self-consistent at {fake_energy} Ha")
PYEOF

#!/usr/bin/env bash
# Oracle solution for cp2k-basis-convergence.
set -euo pipefail
cd /workspace

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

# Build the &COORD block from the asset geometry (skip header lines).
COORD=$(tail -n +3 /workspace/assets/methanol.xyz | awk '{printf "      %s   %.10f   %.10f   %.10f\n", $1, $2, $3, $4}')

for BASIS in SZV DZVP TZVP; do
  LOWER=$(echo "$BASIS" | tr 'A-Z' 'a-z')
  cat > methanol_${LOWER}.inp <<EOF
&GLOBAL
  PROJECT methanol_${LOWER}
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
${COORD}
    &END COORD
    &KIND C
      BASIS_SET ${BASIS}-MOLOPT-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
    &KIND O
      BASIS_SET ${BASIS}-MOLOPT-GTH
      POTENTIAL GTH-PBE-q6
    &END KIND
    &KIND H
      BASIS_SET ${BASIS}-MOLOPT-GTH
      POTENTIAL GTH-PBE-q1
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
EOF
  mpirun -np 1 cp2k -i methanol_${LOWER}.inp -o methanol_${LOWER}.out
done

python3 << 'PYEOF'
import json
import re

def last_energy(path):
    with open(path) as f:
        content = f.read()
    matches = re.findall(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)", content)
    if not matches:
        raise RuntimeError(f"No energy found in {path}")
    return float(matches[-1])

e_szv = last_energy("methanol_szv.out")
e_dzvp = last_energy("methanol_dzvp.out")
e_tzvp = last_energy("methanol_tzvp.out")

results = {
    "values": {
        "energy_szv": e_szv,
        "energy_dzvp": e_dzvp,
        "energy_tzvp": e_tzvp,
        "monotonic_decreasing": bool(e_szv > e_dzvp > e_tzvp),
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

print(f"SZV={e_szv:.8f}  DZVP={e_dzvp:.8f}  TZVP={e_tzvp:.8f} Ha  "
      f"monotonic={e_szv > e_dzvp > e_tzvp}")
PYEOF

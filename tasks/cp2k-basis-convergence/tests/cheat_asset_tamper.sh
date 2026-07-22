#!/usr/bin/env bash
# Informed cheat (asset-tampering): the verifier takes the
# geometry from /workspace/assets/methanol.xyz — an agent-WRITABLE path — and
# uses it both for the log-geometry match and the Layer-5 SZV recompute. A
# forger who replaces methanol with a much cheaper molecule (water) and runs
# the real 3-basis pipeline on it gets logs whose geometry matches the
# (tampered) asset, a monotonically decreasing SZV > DZVP > TZVP series, and
# three-way agreement with the verifier's own recompute.
#
# Must FAIL: refs.json pins sha256(methanol.xyz) and Layer 0 validates it
# before any use — a tampered geometry is a hard fail.
set -euo pipefail
cd /workspace

# Tamper: replace methanol with water (3 atoms instead of 6, ~2x cheaper per
# basis and far fewer basis functions).
cat > /workspace/assets/methanol.xyz << 'EOF'
3
water (tampered asset — replaces methanol)
O   0.000000   0.000000   0.117790
H   0.000000   0.755453  -0.471161
H   0.000000  -0.755453  -0.471161
EOF

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS
export OMP_NUM_THREADS=2

# Run the real 3-basis pipeline on the tampered geometry.
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

print(f"Tampered-asset runs: SZV={e_szv:.8f} DZVP={e_dzvp:.8f} TZVP={e_tzvp:.8f} Ha")
PYEOF

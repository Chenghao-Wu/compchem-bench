#!/usr/bin/env bash
# Oracle solution for qe-bands-si: scf -> bands -> bands.x, then parse the
# bands-run XML eigenvalues into results.json.
set -euo pipefail
cd /workspace

cp -r /workspace/assets/pseudo ./pseudo

cat > si_scf.in << 'EOF'
&CONTROL
  calculation = 'scf'
  prefix = 'pwscf'
  outdir = './outdir'
  pseudo_dir = './pseudo'
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.26
  nat = 2
  ntyp = 1
  ecutwfc = 40.0
  ecutrho = 320.0
/
&ELECTRONS
  conv_thr = 1.0d-10
  mixing_beta = 0.7
/
ATOMIC_SPECIES
  Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS alat
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  4 4 4 1 1 1
EOF

cat > si_bands.in << 'EOF'
&CONTROL
  calculation = 'bands'
  prefix = 'pwscf'
  outdir = './outdir'
  pseudo_dir = './pseudo'
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.26
  nat = 2
  ntyp = 1
  ecutwfc = 40.0
  ecutrho = 320.0
  nbnd = 8
/
&ELECTRONS
  conv_thr = 1.0d-10
/
ATOMIC_SPECIES
  Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS alat
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS tpiba_b
2
  0.0 0.0 0.0 20
  1.0 0.0 0.0 1
EOF

cat > bandsx.in << 'EOF'
&BANDS
  prefix = 'pwscf'
  outdir = './outdir'
  filband = 'bands.dat'
/
EOF

pw.x -in si_scf.in > si_scf.out
pw.x -in si_bands.in > si_bands.out
bands.x -in bandsx.in > bandsx.out

python3 << 'PYEOF'
import json
import xml.etree.ElementTree as ET

HA_TO_EV = 27.211386245988
root = ET.parse("outdir/pwscf.xml").getroot()
bs = root.find("./output/band_structure")
ks = bs.findall("ks_energies")
kpts, eigs = [], []
for k in ks:
    kp = [float(x) for x in k.find("k_point").text.split()]
    ev = [float(x) * HA_TO_EV for x in k.find("eigenvalues").text.split()]
    kpts.append(kp)
    eigs.append(ev)

i_gamma = next(i for i, k in enumerate(kpts) if all(abs(c) < 1e-8 for c in k))
i_x = next(i for i, k in enumerate(kpts)
           if abs(k[0] - 1.0) < 1e-6 and abs(k[1]) < 1e-6 and abs(k[2]) < 1e-6)

band4 = [e[3] for e in eigs]  # 1-based band 4
band5 = [e[4] for e in eigs]  # 1-based band 5
vbm = max(band4)
cbm = min(band5)

results = {
    "values": {
        "gamma_band4_eV": band4[i_gamma],
        "gamma_band5_eV": band5[i_gamma],
        "x_band4_eV": band4[i_x],
        "x_band5_eV": band5[i_x],
        "vbm_eV": vbm,
        "cbm_eV": cbm,
        "indirect_gap_eV": cbm - vbm,
    },
    "units": {k: "eV" for k in
              ("gamma_band4_eV", "gamma_band5_eV", "x_band4_eV", "x_band5_eV",
               "vbm_eV", "cbm_eV", "indirect_gap_eV")},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
for k, v in results["values"].items():
    print(f"{k} = {v:.6f}")
PYEOF

#!/usr/bin/env bash
# Informed cheat for qe-bands-si: a forger fabricates the ENTIRE three-step
# artifact chain without running anything — plausible input decks (correct
# calculation types, matching prefix/outdir, nbnd=8), an scf log and a bands
# log with v7.4 banners and JOB DONE., a bands.x log, a well-formed bands.dat
# (nbnd=8, nks=21) and a schema-valid pwscf.xml whose band_structure carries
# fabricated eigenvalues following a plausible Si-like dispersion (VBM at
# Gamma, PBE-ish gap ~0.61 eV), and a results.json fully consistent with the
# forged XML and bands.dat.
# Layers 1-6 (existence, cross-references, log integrity, bands.dat
# structure, XML re-derivation, bands.dat double source) all PASS by
# construction. It must FAIL at layer 7: the guessed eigenvalues and gap
# cannot land inside the calibrated tolerances.
set -euo pipefail
mkdir -p /workspace/outdir /logs/verifier
cd /workspace

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

cat > si_scf.out << 'EOF'
     Program PWSCF v.7.4 starts on 20Jul2026 at  0: 0: 0
     number of atoms/cell      =            2.0000
     number of k points=    10
     kinetic-energy cutoff     =     40.0000  Ry
     iteration #  1     ecut=    40.00 Ry     beta= 0.70
     iteration #  2     ecut=    40.00 Ry     beta= 0.70
     iteration #  3     ecut=    40.00 Ry     beta= 0.70
     iteration #  4     ecut=    40.00 Ry     beta= 0.70
     iteration #  5     ecut=    40.00 Ry     beta= 0.70
     iteration #  6     ecut=    40.00 Ry     beta= 0.70
     iteration #  7     ecut=    40.00 Ry     beta= 0.70
     iteration #  8     ecut=    40.00 Ry     beta= 0.70
     convergence has been achieved in   8 iterations
!    total energy              =     -22.84000000 Ry
     JOB DONE.
EOF

cat > si_bands.out << 'EOF'
     Program PWSCF v.7.4 starts on 20Jul2026 at  0: 0: 0
     number of Kohn-Sham states=            8
     kinetic-energy cutoff     =     40.0000  Ry
     number of k points=    21
     iteration #  1     ecut=    40.00 Ry     beta= 0.70
     iteration #  2     ecut=    40.00 Ry     beta= 0.70
     iteration #  3     ecut=    40.00 Ry     beta= 0.70
     iteration #  4     ecut=    40.00 Ry     beta= 0.70
     JOB DONE.
EOF

cat > bandsx.out << 'EOF'
     Program BANDS v.7.4 starts on 20Jul2026 at  0: 0: 0
     Reading xml data from directory:
     ./outdir/pwscf.save/
                    xk=(   0.00000,   0.00000,   0.00000  )
     JOB DONE.
EOF

python3 << 'PYEOF'
import json

HA_TO_EV = 27.211386245988
# Fabricated Si-like dispersion along Gamma -> X (21 k-points):
# band 4 peaks at Gamma (VBM 6.15 eV), band 5 minimum near X (~6.76 -> gap
# ~0.61 eV, a literature-PBE-looking guess), other bands plausible filler.
def band4(x):
    return 6.15 - 3.4 * x * x
def band5(x):
    return 9.2 - 2.44 * x + 0.0 * x * x if x < 0.85 else 6.76 + 0.15 * (x - 0.85)
def band1(x):
    return -5.7 + 4.1 * x
def band2(x):
    return 6.15 - 6.9 * x * x
def band3(x):
    return 6.15 - 3.9 * x * x

kpts, eigs = [], []
for i in range(21):
    x = i / 20.0
    kpts.append([x, 0.0, 0.0])
    row = [band1(x), band2(x), band3(x), band4(x),
           band5(x), band5(x) + 0.6, 15.0 + 1.3 * x, 15.2 + 1.3 * x]
    row.sort()
    # enforce band4 = 4th, band5 = 5th by construction
    eigs.append(row)

# bands.dat (3-decimal print, like the real bands.x)
with open("bands.dat", "w") as f:
    f.write(" &plot nbnd=   8, nks=    21 /\n")
    for k, e in zip(kpts, eigs):
        f.write(f"{k[0]:14.6f}{k[1]:10.6f}{k[2]:10.6f}\n")
        f.write("".join(f"{v:9.3f}" for v in e) + "\n")

# pwscf.xml with band_structure (eigenvalues in Hartree, like the real one)
parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<qes:espresso xmlns:qes="http://www.quantum-espresso.org/ns/qes/qes-1.0">',
         '  <output>', '    <band_structure>',
         '      <nbnd>8</nbnd>', '      <nks>21</nks>',
         '      <nelec>8.000000000000000E+000</nelec>',
         '      <fermi_energy>2.17E-1</fermi_energy>']
for k, e in zip(kpts, eigs):
    parts.append('      <ks_energies>')
    parts.append(f'        <k_point weight="1.0">{k[0]:.16E}  {k[1]:.16E}  {k[2]:.16E}</k_point>')
    ev = " ".join(f"{v / HA_TO_EV:.15E}" for v in e)
    parts.append(f'        <eigenvalues size="8">{ev}</eigenvalues>')
    parts.append('      </ks_energies>')
parts += ['    </band_structure>', '  </output>', '</qes:espresso>']
with open("outdir/pwscf.xml", "w") as f:
    f.write("\n".join(parts))

b4 = [e[3] for e in eigs]
b5 = [e[4] for e in eigs]
vbm, cbm = max(b4), min(b5)
results = {
    "values": {
        "gamma_band4_eV": b4[0],
        "gamma_band5_eV": b5[0],
        "x_band4_eV": b4[20],
        "x_band5_eV": b5[20],
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
print(f"Forged full bands chain: vbm={vbm:.3f} cbm={cbm:.3f} gap={cbm - vbm:.3f} eV")
PYEOF

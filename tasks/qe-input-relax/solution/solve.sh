#!/usr/bin/env bash
# Oracle solution for qe-input-relax: write a valid vc-relax deck for
# zinc-blende SiC meeting every stated requirement, using the provided
# pseudopotentials (copied next to the input).
set -euo pipefail
cd /workspace

cp -r /workspace/assets/pseudo ./pseudo

cat > sic_vc_relax.in << 'EOF'
&CONTROL
  calculation = 'vc-relax'
  prefix = 'sic'
  outdir = './outdir'
  pseudo_dir = './pseudo'
  forc_conv_thr = 1.0d-4
/
&SYSTEM
  ibrav = 2
  A = 4.3596
  nat = 2
  ntyp = 2
  ecutwfc = 50.0
  ecutrho = 400.0
/
&ELECTRONS
  conv_thr = 1.0d-8
  mixing_beta = 0.7
/
&IONS
  ion_dynamics = 'bfgs'
/
&CELL
  cell_dynamics = 'bfgs'
/
ATOMIC_SPECIES
  Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
  C  12.0107 C.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  C  0.25 0.25 0.25
K_POINTS automatic
  4 4 4 1 1 1
EOF

echo "Wrote /workspace/sic_vc_relax.in"

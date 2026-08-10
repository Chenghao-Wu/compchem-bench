#!/usr/bin/env bash
# Oracle solution for lammps-thermal-conductivity.
#
# This is a "correct agent": it generates the 1200-bead system with the provided
# template script, writes its own LAMMPS inputs for the two-stage equilibration
# (T*=1.0 then quench to T*=0.4) and for the T*=0.4 Green-Kubo production run,
# then computes kappa with the reference protocol.
#
# The whole pipeline is deterministic (fixed generator RNG, fixed Langevin seeds,
# single-threaded lmp_serial on the pinned CI image), so the reference kappa is
# exact for the image.
set -euo pipefail
cd /workspace

cp /workspace/assets/generate_bench_system.py ./generate_bench_system.py
cp /workspace/assets/bead2.tersoff ./bead2.tersoff

# NVT equilibration steps per stage (override with EQ_STEPS for calibration).
EQ_STEPS="${EQ_STEPS:-250000}"
# Langevin seed (fixed -> deterministic).
EQ_SEED="${EQ_SEED:-8675309}"

export OMP_NUM_THREADS=1

# ---- 1. generate the 1200-bead initial coil (deterministic) ------------------
python3 generate_bench_system.py data.in

# ---- 2. write the equilibration input. All of T / suffix / inp / nrun / seed
#         are supplied via the -var command-line switches. ----------------------
cat > equilibrate.in << 'EQEOF'
units           lj
atom_style      molecular
boundary        p p p
dimension       3

bond_style      fene
angle_style     cosine
pair_style      hybrid/overlay lj/cut 1.1225 tersoff

read_data       ${inp}

special_bonds   fene
bond_coeff      * 30.0 1.5 1.0 1.0
angle_coeff     * 1.5
pair_coeff      * * tersoff bead2.tersoff NULL B1
pair_coeff      * * lj/cut 0.0 1.0 1.1225
pair_coeff      1 * lj/cut 1.0 1.0 1.1225

timestep        0.005
neighbor        0.3 bin

minimize        1.0e-5 1.0e-7 1000 10000

velocity        all create ${T} ${seed} dist gaussian

thermo          10000
thermo_style    custom step temp pe ke etotal press

fix             1 all nve
fix             2 all langevin ${T} ${T} 100 ${seed}
fix             3 all momentum 100 linear 1 1 1

run             ${nrun}

write_data      data_${suffix}.lammps
EQEOF

# ---- 3. stage 1: equilibrate at T*=1.0 from the generated coil ---------------
lmp_serial -var T 1.0 -var suffix T1 -var inp data.in -var nrun "$EQ_STEPS" \
           -var seed "$EQ_SEED" -log log.eq_T1 -in equilibrate.in

# ---- 4. stage 2: quench to T*=0.4 STARTING FROM the T*=1.0 state -------------
lmp_serial -var T 0.4 -var suffix T04 -var inp data_T1.lammps -var nrun "$EQ_STEPS" \
           -var seed "$EQ_SEED" -log log.eq_T04 -in equilibrate.in

# ---- 5. write the production input (T*=0.4, NVE, Green-Kubo) -----------------
cat > therm.in << 'THERM'
units           lj
atom_style      molecular
boundary        p p p
dimension       3

bond_style      fene
angle_style     cosine
pair_style      hybrid/overlay lj/cut 1.1225 tersoff

read_data       data_T04.lammps

special_bonds   fene
bond_coeff      * 30.0 1.5 1.0 1.0
angle_coeff     * 1.5
pair_coeff      * * tersoff bead2.tersoff NULL B1
pair_coeff      * * lj/cut 0.0 1.0 1.1225
pair_coeff      1 * lj/cut 1.0 1.0 1.1225

variable        dt equal 0.005
timestep        ${dt}
neighbor        0.3 bin

thermo          2000
thermo_style    custom step temp ke pe etotal press

velocity        all zero linear
fix             1 all nve
fix             mom all momentum 100 linear 1 1 1

compute         myKE all ke/atom
compute         myPE all pe/atom
compute         myStress all stress/atom NULL virial
compute         flux all heat/flux myKE myPE myStress

variable        Jx equal c_flux[1]
variable        Jy equal c_flux[2]
variable        Jz equal c_flux[3]
variable        tstep equal step
fix             jout all print 5 "${tstep} ${Jx} ${Jy} ${Jz}" &
                file flux_T04.dat screen no title "# step Jx Jy Jz"

fix             JJ all ave/correlate 5 200 25000 &
                c_flux[1] c_flux[2] c_flux[3] &
                type auto file J0Jt_T04.dat ave one

run             200000
THERM

lmp_serial -log log.T04 -in therm.in

# ---- 6. analysis: kappa at T*=0.4 by the reference protocol ------------------
python3 << 'PYEOF'
import json
import numpy as np

DT = 0.005
NEVERY = 5
DT_DATA = NEVERY * DT          # lag spacing in tau
KBT = 1.0
NC_REF = 5001                  # full-block Ncount at lag 0 = Nfreq/Nevery + 1
WINDOW = 10
NLAGS = 200


def parse_acf(path):
    blocks = []
    cur = None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) == 2:
                try:
                    int(parts[0]); int(parts[1])
                except ValueError:
                    continue
                cur = []
                blocks.append(cur)
                continue
            if len(parts) >= 6 and cur is not None:
                try:
                    row = [float(x) for x in parts[:6]]
                except ValueError:
                    continue
                cur.append(row)
    return blocks


def box_volume(path):
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 4 and p[2] in ("xlo", "ylo", "zlo"):
                x0, x1 = float(p[0]), float(p[1])
                if p[2] == "xlo":
                    lx = x1 - x0
                elif p[2] == "ylo":
                    ly = x1 - x0
                else:
                    lz = x1 - x0
            if p[:1] == ["Atoms"]:
                break
    return lx * ly * lz


def kappa_from_acf(path, V, T):
    blocks = parse_acf(path)
    full = [b for b in blocks if len(b) >= NLAGS and b[0][2] >= NC_REF]
    if not full:
        raise RuntimeError(f"no complete blocks in {path}")

    G = np.zeros(NLAGS)
    for b in full:
        a = np.array(b)[:NLAGS]
        G += a[:, 3] + a[:, 4] + a[:, 5]
    G /= len(full)

    Gn = G / G[0]
    smooth = np.convolve(Gn, np.ones(WINDOW) / WINDOW, mode="valid")
    zeros = np.where(smooth < 0)[0]
    cutoff = int(round((zeros[0] + WINDOW) * 1.5)) if len(zeros) else NLAGS
    cutoff = min(cutoff, NLAGS)

    def kappa_curve(g):
        integ = np.cumsum(g[:cutoff]) * DT_DATA
        curve = integ / (3.0 * KBT * T * T * V)
        return curve[int(len(curve) * 0.8):]

    k = float(np.mean(kappa_curve(G)))

    kb = []
    for b in full:
        a = np.array(b)[:NLAGS]
        gb = a[:, 3] + a[:, 4] + a[:, 5]
        kb.append(float(np.mean(kappa_curve(gb))))
    err = float(np.std(kb, ddof=1) / np.sqrt(len(kb))) if len(kb) > 1 else 0.0
    return k, err, len(full)


V = box_volume("data_T04.lammps")
k, e, n = kappa_from_acf("J0Jt_T04.dat", V, 0.4)

results = {
    "values": {
        "kappa_T04": k,
        "kappa_err_T04": e,
        "n_blocks": n,
    },
    "units": {
        "kappa_T04": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
        "n_blocks": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"T=0.4 : kappa = {k:.6f} ± {e:.6f}  (n_blocks={n}, V={V:.4f})")
PYEOF

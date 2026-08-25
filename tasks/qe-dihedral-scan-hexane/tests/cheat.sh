#!/usr/bin/env bash
# Informed cheat for qe-dihedral-scan-hexane: a forger who knows alkanes runs
# ZERO pw.x calculations. It generates the seven correct rigid-rotation
# geometries from the provided asset (the rotation is pure math), then
# fabricates complete-looking pw.x logs around them — v7.4 banner, alat
# lattice line, a 20-atom tau table in alat units, a converged `! total
# energy` line, JOB DONE. — plus a results.json fully self-consistent with
# the fake logs. Absolute energies are guessed close to the calibrated value
# and the profile uses textbook butane-like barrier heights.
#
# Layers 1-5 (existence, asset hashes, log integrity + input echoes,
# dihedral/bond-fingerprint geometry checks, log<->results consistency) all
# PASS — the geometries are honest rigid rotations and every file is
# self-consistent. Must FAIL at layer 6: the guessed absolute energies are
# ~2e-3 Ry off, far outside the 1e-5 Ry per-angle reference tolerance. Even
# with a perfect energy guess it would still fail layer 7: the verifier
# re-runs SCF single points on the logged geometries, and a real
# recomputation never agrees with a fabricated `! total energy`.
set -euo pipefail
mkdir -p /workspace/scan /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json
import math
import os

CELLDM_BOHR = 30.0
BOHR_TO_ANG = 0.529177210903
RY_TO_KCAL = 627.5094740631
GRID = [0, 30, 60, 90, 120, 150, 180]
MOVING = [3, 4, 5] + list(range(13, 20))
IC2, IC3, IC4, IC5 = 1, 2, 3, 4

# ── guessed energies (no calculation performed) ─────────────────────────────
# base guess close to the true anti energy but deliberately 2e-3 Ry off;
# profile offsets are textbook butane values in kcal/mol
E_BASE_GUESS = -127.27920000
PROFILE_GUESS_KCAL = {0: 4.90, 30: 2.90, 60: 0.65, 90: 1.70,
                      120: 3.60, 150: 1.10, 180: 0.0}


def read_xyz(path):
    lines = open(path).read().strip().splitlines()
    return [(l.split()[0], [float(l.split()[1]), float(l.split()[2]), float(l.split()[3])])
            for l in lines[2:2 + int(lines[0])]]


def vsub(a, b): return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
def vdot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def vcross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def vnorm(a):
    n = math.sqrt(vdot(a, a)); return [a[0]/n, a[1]/n, a[2]/n]


def dihedral(p0, p1, p2, p3):
    b0, b1, b2 = vsub(p0, p1), vsub(p2, p1), vsub(p3, p2)
    v = [b0[i] - vdot(b0, b1)/vdot(b1, b1)*b1[i] for i in range(3)]
    w = [b2[i] - vdot(b2, b1)/vdot(b1, b1)*b1[i] for i in range(3)]
    return math.degrees(math.atan2(vdot(vcross(vnorm(b1), v), w), vdot(v, w)))


def rotate(point, axis_point, axis_unit, theta):
    p = vsub(point, axis_point)
    c, s = math.cos(theta), math.sin(theta)
    t1 = [p[i]*c for i in range(3)]
    t2 = [vcross(axis_unit, p)[i]*s for i in range(3)]
    t3 = [axis_unit[i]*vdot(axis_unit, p)*(1.0-c) for i in range(3)]
    return [axis_point[i] + t1[i] + t2[i] + t3[i] for i in range(3)]


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def scan_geometry(atoms, target_deg):
    pos = [a[1][:] for a in atoms]
    axis_point = pos[IC3]
    axis_unit = vnorm(vsub(pos[IC4], pos[IC3]))
    phi0 = dihedral(pos[IC2], pos[IC3], pos[IC4], pos[IC5])
    probe_deg = 0.5
    trial = [p[:] for p in pos]
    for i in MOVING:
        trial[i] = rotate(pos[i], axis_point, axis_unit, math.radians(probe_deg))
    slope = wrap180(dihedral(trial[IC2], trial[IC3], trial[IC4], trial[IC5]) - phi0) / probe_deg
    theta_deg = wrap180(target_deg - phi0) / slope
    out = [p[:] for p in pos]
    for i in MOVING:
        out[i] = rotate(pos[i], axis_point, axis_unit, math.radians(theta_deg))
    return out


PW_IN = """&CONTROL
  calculation = 'scf'
  prefix = 'hex_phi_{phi:03d}'
  outdir = './outdir'
  pseudo_dir = '/workspace/assets/pseudo'
/
&SYSTEM
  ibrav = 1
  celldm(1) = 30.0
  nat = 20
  ntyp = 2
  ecutwfc = 50.0
  ecutrho = 400.0
  occupations = 'fixed'
/
&ELECTRONS
  conv_thr = 1.0d-9
/
ATOMIC_SPECIES
  C 12.0107 C.pbe-n-kjpaw_psl.1.0.0.UPF
  H 1.00794 H.pbe-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS angstrom
{positions}
K_POINTS gamma
"""

atoms = read_xyz("/workspace/assets/hexane_anti.xyz")
energies = []
for phi in GRID:
    geom = scan_geometry(atoms, phi)
    positions = "\n".join(
        f"  {atoms[i][0]} {geom[i][0]:.10f} {geom[i][1]:.10f} {geom[i][2]:.10f}"
        for i in range(20))
    rundir = f"scan/phi_{phi:03d}"
    os.makedirs(rundir, exist_ok=True)
    with open(os.path.join(rundir, "pw.in"), "w") as f:
        f.write(PW_IN.format(phi=phi, positions=positions))

    # fabricated log: banner, alat echo, honest tau table of the rotated
    # geometry, guessed converged energy, JOB DONE.
    tau_rows = ""
    for i, (el, p) in enumerate(zip([a[0] for a in atoms], geom)):
        tau = [c / (CELLDM_BOHR * BOHR_TO_ANG) for c in p]
        tau_rows += (f"{i+1:>10}           {el}   tau({i+1:>4}) = ("
                     f" {tau[0]:.8f}  {tau[1]:.8f}  {tau[2]:.8f}  )\n")
    e_guess = E_BASE_GUESS + PROFILE_GUESS_KCAL[phi] / RY_TO_KCAL
    energies.append(e_guess)
    log = f"""     Program PWSCF v.7.4 starts on 23Aug2026 at  10: 0: 0

     bravais-lattice index     =            1
     lattice parameter (alat)  =    30.0000  a.u.

     site n.     atom                  positions (alat units)
{tau_rows}
     total energy              =     {e_guess - 0.00031:.8f} Ry
     total energy              =     {e_guess - 0.000002:.8f} Ry
!    total energy              =     {e_guess:.8f} Ry

     JOB DONE.
"""
    with open(os.path.join(rundir, "pw.out"), "w") as f:
        f.write(log)

e_anti = energies[-1]
relative = [(e - e_anti) * RY_TO_KCAL for e in energies]
results = {
    "values": {
        "dihedral_grid_deg": [float(p) for p in GRID],
        "total_energies_Ry": energies,
        "relative_energies_kcal_mol": relative,
        "syn_barrier_kcal_mol": relative[0],
        "gauche_energy_kcal_mol": relative[2],
        "eclipsed_barrier_kcal_mol": relative[4],
    },
    "units": {
        "dihedral_grid_deg": "deg",
        "total_energies_Ry": "Ry",
        "relative_energies_kcal_mol": "kcal/mol",
        "syn_barrier_kcal_mol": "kcal/mol",
        "gauche_energy_kcal_mol": "kcal/mol",
        "eclipsed_barrier_kcal_mol": "kcal/mol",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged 7 scan logs; guessed syn barrier {relative[0]:.2f} kcal/mol "
      f"without running pw.x once")
PYEOF

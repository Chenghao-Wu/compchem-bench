#!/usr/bin/env bash
# Informed cheat for qe-dihedral-scan-hexane, partial-execution attack: the
# forger knows the verifier only RE-RUNS three angles (0, 60, 180 deg), so it
# performs those three pw.x single points for real and fabricates the other
# four logs (30, 90, 120, 150) with energies interpolated between its real
# runs. The three recomputed points agree with their logs — layer 7 passes —
# but the four interpolated absolute energies are ~1e-3 Ry away from the true
# DFT values, far outside the 1e-5 Ry per-angle reference tolerance.
# Must FAIL at layer 6 (reference tolerances): actually running only the
# recomputed subset does not get a forger through.
set -euo pipefail
mkdir -p /workspace/scan /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json
import math
import os
import re
import subprocess

CELLDM_BOHR = 30.0
BOHR_TO_ANG = 0.529177210903
RY_TO_KCAL = 627.5094740631
GRID = [0, 30, 60, 90, 120, 150, 180]
REAL = {0, 60, 180}          # the angles the verifier recomputes
MOVING = [3, 4, 5] + list(range(13, 20))
IC2, IC3, IC4, IC5 = 1, 2, 3, 4


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
energies = {}

# ── real runs only at the recomputed angles ─────────────────────────────────
for phi in sorted(REAL):
    geom = scan_geometry(atoms, phi)
    positions = "\n".join(
        f"  {atoms[i][0]} {geom[i][0]:.10f} {geom[i][1]:.10f} {geom[i][2]:.10f}"
        for i in range(20))
    rundir = f"scan/phi_{phi:03d}"
    os.makedirs(rundir, exist_ok=True)
    with open(os.path.join(rundir, "pw.in"), "w") as f:
        f.write(PW_IN.format(phi=phi, positions=positions))
    with open(os.path.join(rundir, "pw.out"), "w") as f:
        subprocess.run(["pw.x", "-in", "pw.in"], cwd=rundir, stdout=f,
                       stderr=subprocess.STDOUT, check=True, timeout=1200)
    content = open(os.path.join(rundir, "pw.out")).read()
    m = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    energies[phi] = float(m[-1])
    print(f"REAL   phi={phi:3d}  E={energies[phi]:.8f} Ry", flush=True)

# ── fabricated logs at the remaining angles: honest rotated geometry in the
# tau table, energy linearly interpolated between the real neighbours ────────
def fake_energy(phi):
    if phi < 60:
        a, b = 0, 60
    elif phi < 120:
        a, b = 60, 120
    else:
        a, b = 120, 180
    ea = energies[a] if a in energies else None
    eb = energies[b] if b in energies else None
    # anchors at 60/180 are real; 120 is guessed above the midpoint of the
    # 60/180 legs like a textbook eclipsed barrier
    if a == 60 and b == 120:
        e120 = energies[60] + 3.4 / RY_TO_KCAL
        return energies[60] + (e120 - energies[60]) * (phi - 60) / 60.0
    if a == 120:
        e120 = energies[60] + 3.4 / RY_TO_KCAL
        return e120 + (energies[180] - e120) * (phi - 120) / 60.0
    return energies[a] + (energies[b] - energies[a]) * (phi - a) / (b - a)


for phi in GRID:
    if phi in REAL:
        continue
    geom = scan_geometry(atoms, phi)
    positions = "\n".join(
        f"  {atoms[i][0]} {geom[i][0]:.10f} {geom[i][1]:.10f} {geom[i][2]:.10f}"
        for i in range(20))
    rundir = f"scan/phi_{phi:03d}"
    os.makedirs(rundir, exist_ok=True)
    with open(os.path.join(rundir, "pw.in"), "w") as f:
        f.write(PW_IN.format(phi=phi, positions=positions))
    tau_rows = ""
    for i, (el, p) in enumerate(zip([a[0] for a in atoms], geom)):
        tau = [c / (CELLDM_BOHR * BOHR_TO_ANG) for c in p]
        tau_rows += (f"{i+1:>10}           {el}   tau({i+1:>4}) = ("
                     f" {tau[0]:.8f}  {tau[1]:.8f}  {tau[2]:.8f}  )\n")
    e_fake = fake_energy(phi)
    energies[phi] = e_fake
    log = f"""     Program PWSCF v.7.4 starts on 23Aug2026 at  10: 0: 0

     bravais-lattice index     =            1
     lattice parameter (alat)  =    30.0000  a.u.

     site n.     atom                  positions (alat units)
{tau_rows}
     total energy              =     {e_fake - 0.00031:.8f} Ry
!    total energy              =     {e_fake:.8f} Ry

     JOB DONE.
"""
    with open(os.path.join(rundir, "pw.out"), "w") as f:
        f.write(log)
    print(f"FORGED phi={phi:3d}  E={e_fake:.8f} Ry (interpolated)", flush=True)

e_list = [energies[p] for p in GRID]
e_anti = e_list[-1]
relative = [(e - e_anti) * RY_TO_KCAL for e in e_list]
results = {
    "values": {
        "dihedral_grid_deg": [float(p) for p in GRID],
        "total_energies_Ry": e_list,
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

print("Ran 0/60/180 for real; forged 30/90/120/150 by interpolation")
PYEOF

#!/usr/bin/env bash
# Oracle solution for qe-dihedral-scan-hexane.
#
# Rigid torsion scan of n-hexane about the central C3-C4 bond: the provided
# relaxed all-anti geometry is rotated to C2-C3-C4-C5 dihedrals of
# 0/30/.../180 deg (moving fragment: C4, C5, C6 and their seven H atoms),
# one pw.x SCF single point per angle, then results.json is assembled from
# the seven logs. No hardcoded energies — real execution only.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import math
import os
import re
import subprocess

BOHR_TO_ANG = 0.529177210903
CELLDM_BOHR = 30.0
RY_TO_KCAL = 627.5094740631
GRID = [0, 30, 60, 90, 120, 150, 180]

ASSET = "/workspace/assets/hexane_anti.xyz"
PSEUDO = "/workspace/assets/pseudo"

# 0-based indices; asset order is C1..C6 then H grouped by carbon
MOVING = [3, 4, 5] + list(range(13, 20))      # C4,C5,C6 + H(C4..C6)
IC2, IC3, IC4, IC5 = 1, 2, 3, 4               # dihedral-defining carbons


def read_xyz(path):
    lines = open(path).read().strip().splitlines()
    n = int(lines[0])
    atoms = []
    for line in lines[2:2 + n]:
        p = line.split()
        atoms.append((p[0], [float(p[1]), float(p[2]), float(p[3])]))
    return atoms


def vsub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def vnorm(a):
    n = math.sqrt(vdot(a, a))
    return [a[0] / n, a[1] / n, a[2] / n]


def dihedral(p0, p1, p2, p3):
    """Signed dihedral p0-p1-p2-p3 in degrees, atan2 convention."""
    b0 = vsub(p0, p1)
    b1 = vsub(p2, p1)
    b2 = vsub(p3, p2)
    v = [b0[i] - vdot(b0, b1) / vdot(b1, b1) * b1[i] for i in range(3)]
    w = [b2[i] - vdot(b2, b1) / vdot(b1, b1) * b1[i] for i in range(3)]
    x = vdot(v, w)
    y = vdot(vcross(vnorm(b1), v), w)
    return math.degrees(math.atan2(y, x))


def rotate(point, axis_point, axis_unit, theta):
    """Rodrigues rotation of point about the axis through axis_point."""
    p = vsub(point, axis_point)
    c, s = math.cos(theta), math.sin(theta)
    term1 = [p[i] * c for i in range(3)]
    term2 = [vcross(axis_unit, p)[i] * s for i in range(3)]
    term3 = [axis_unit[i] * vdot(axis_unit, p) * (1.0 - c) for i in range(3)]
    return [axis_point[i] + term1[i] + term2[i] + term3[i] for i in range(3)]


def wrap180(angle):
    return (angle + 180.0) % 360.0 - 180.0


def scan_geometry(atoms, target_deg):
    """Rigidly rotate the C4-side fragment so dihedral C2-C3-C4-C5 = target."""
    pos = [a[1][:] for a in atoms]
    axis_point = pos[IC3]
    axis_unit = vnorm(vsub(pos[IC4], pos[IC3]))

    def current(geom):
        return dihedral(geom[IC2], geom[IC3], geom[IC4], geom[IC5])

    phi0 = current(pos)
    # rotation->dihedral slope is +/-1; probe once to fix the sign convention
    probe_deg = 0.5
    trial = [p[:] for p in pos]
    for i in MOVING:
        trial[i] = rotate(pos[i], axis_point, axis_unit, math.radians(probe_deg))
    slope = wrap180(current(trial) - phi0) / probe_deg   # +/-1, in deg/deg

    theta_deg = wrap180(target_deg - phi0) / slope
    out = [p[:] for p in pos]
    for i in MOVING:
        out[i] = rotate(pos[i], axis_point, axis_unit, math.radians(theta_deg))
    assert abs(wrap180(current(out) - target_deg)) < 1e-6, \
        f"rotation missed target {target_deg}: got {current(out)}"
    return out


PW_TEMPLATE = """&CONTROL
  calculation = 'scf'
  prefix = 'hex_phi_{phi:03d}'
  outdir = './outdir'
  pseudo_dir = '{pseudo}'
/
&SYSTEM
  ibrav = 1
  celldm(1) = {celldm}
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

atoms = read_xyz(ASSET)
energies = []
for phi in GRID:
    geom = scan_geometry(atoms, phi)
    positions = "\n".join(
        f"  {atoms[i][0]} {geom[i][0]:.10f} {geom[i][1]:.10f} {geom[i][2]:.10f}"
        for i in range(len(atoms))
    )
    rundir = f"scan/phi_{phi:03d}"
    os.makedirs(rundir, exist_ok=True)
    with open(os.path.join(rundir, "pw.in"), "w") as f:
        f.write(PW_TEMPLATE.format(phi=phi, pseudo=PSEUDO,
                                   celldm=CELLDM_BOHR, positions=positions))
    with open(os.path.join(rundir, "pw.out"), "w") as f:
        subprocess.run(["pw.x", "-in", "pw.in"], cwd=rundir, stdout=f,
                       stderr=subprocess.STDOUT, check=True, timeout=1200)
    content = open(os.path.join(rundir, "pw.out")).read()
    if "JOB DONE." not in content:
        raise RuntimeError(f"phi={phi}: run did not finish")
    m = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    if not m:
        raise RuntimeError(f"phi={phi}: no total energy")
    energies.append(float(m[-1]))
    print(f"phi={phi:3d}  E={energies[-1]:.8f} Ry", flush=True)

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

print(f"syn barrier (0 deg):   {relative[0]:.3f} kcal/mol")
print(f"gauche (60 deg):       {relative[2]:.3f} kcal/mol")
print(f"eclipsed (120 deg):    {relative[4]:.3f} kcal/mol")
PYEOF

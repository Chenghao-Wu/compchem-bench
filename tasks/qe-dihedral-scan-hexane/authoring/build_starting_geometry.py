#!/usr/bin/env python3
"""
Deterministic builder for the idealized all-anti n-hexane starting geometry.

Pure-python (stdlib only), fully deterministic: no randomness, no dates.
Bonds/angles are textbook ideal values (C-C 1.54 Angstrom, C-H 1.09 Angstrom,
tetrahedral angle 109.4712206 deg); the carbon skeleton is a planar all-anti
zigzag. Terminal methyls carry one C-H bond anti-periplanar across the C-C
bond, so the idealized point-group symmetry (skeleton mirror plane + inversion
center) is exact.

This is ONLY the starting guess: `environment/assets/hexane_anti.xyz` is the
pw.x-relaxed descendant of this structure (same DFT settings as the scan),
recentred so the C3-C4 bond midpoint sits at the centre of the 30-bohr cubic
cell. See authoring/README.md for the full provenance chain.

Usage:  python3 authoring/build_starting_geometry.py
Writes: authoring/hexane_idealized.xyz

Atom order (fixed convention, also used by the task instruction and verifier):
  atoms  1- 6 : C1 ... C6 (chain order)
  atoms  7- 9 : 3 x H on C1
  atoms 10-11 : 2 x H on C2
  atoms 12-13 : 2 x H on C3
  atoms 14-15 : 2 x H on C4
  atoms 16-17 : 2 x H on C5
  atoms 18-20 : 3 x H on C6
"""

import math
import os

R_CC = 1.540           # Angstrom
R_CH = 1.090           # Angstrom
TET = math.radians(109.47122063449069)   # tetrahedral angle

# cos(109.47deg) = -1/3 exactly for the ideal tetrahedron; the zigzag bond
# directions alternate at +/- (TET/2 - 45deg)... derived closed form below:
# bond direction k makes angle +/- alpha with the chain (x) axis, where
# alpha = (180deg - TET)/2 so that the interior C-C-C angle is TET.
ALPHA = (math.pi - TET) / 2.0


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vnorm(a):
    n = math.sqrt(vdot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def carbon_skeleton():
    """Planar all-anti zigzag of 6 carbons, chain axis along x, in the xy plane."""
    carbons = [(0.0, 0.0, 0.0)]
    for k in range(5):  # 5 C-C bonds
        sign = +1.0 if k % 2 == 0 else -1.0
        d = (math.cos(sign * ALPHA), math.sin(sign * ALPHA), 0.0)
        carbons.append(vadd(carbons[-1], vscale(d, R_CC)))
    return carbons


def methylene_hydrogens(c_prev, c_here, c_next):
    """Two exact tetrahedral H directions for an interior (CH2) carbon."""
    u1 = vnorm(vsub(c_prev, c_here))
    u2 = vnorm(vsub(c_next, c_here))
    # Solve h.u1 = h.u2 = -1/3, h_a.h_b = -1/3:
    # h = -0.5*(u1+u2) +/- sqrt(2/3) * normalize(u1 x u2)
    base = vscale(vadd(u1, u2), -0.5)
    off = vscale(vnorm(vcross(u1, u2)), math.sqrt(2.0 / 3.0))
    return [vadd(base, off), vsub(base, off)]


def methyl_hydrogens(c_here, c_next, c_nextnext):
    """Three staggered H directions for a terminal (CH3) carbon.

    One H is placed anti-periplanar across the C-C bond (H-C-C-C dihedral
    exactly 180 deg), the other two at +/-120 deg around the bond axis.
    """
    u = vnorm(vsub(c_next, c_here))          # bond direction toward the chain
    v = vnorm(vsub(c_nextnext, c_next))      # next bond direction along the chain
    # In-plane unit vector perpendicular to u, on the ANTI side of the
    # C(here)-C(next)-C(nextnext) plane:
    w = vsub(v, vscale(u, vdot(v, u)))
    e1 = vscale(vnorm(w), -1.0)
    e2 = vnorm(vcross(u, e1))
    hs = []
    for phi in (0.0, 2.0 * math.pi / 3.0, -2.0 * math.pi / 3.0):
        # h = -u/3 + (2*sqrt(2)/3) * (cos(phi) e1 + sin(phi) e2)
        radial = vadd(vscale(e1, math.cos(phi)), vscale(e2, math.sin(phi)))
        h = vadd(vscale(u, -1.0 / 3.0), vscale(radial, 2.0 * math.sqrt(2.0) / 3.0))
        hs.append(h)
    return hs


def main():
    carbons = carbon_skeleton()
    atoms = [("C", c) for c in carbons]

    # Methyl groups (C1 and C6)
    for h in methyl_hydrogens(carbons[0], carbons[1], carbons[2]):
        atoms.append(("H", vadd(carbons[0], vscale(h, R_CH))))
    # Methylene groups (C2..C5)
    for i in range(1, 5):
        for h in methylene_hydrogens(carbons[i - 1], carbons[i], carbons[i + 1]):
            atoms.append(("H", vadd(carbons[i], vscale(h, R_CH))))
    for h in methyl_hydrogens(carbons[5], carbons[4], carbons[3]):
        atoms.append(("H", vadd(carbons[5], vscale(h, R_CH))))

    assert len(atoms) == 20, f"expected 20 atoms, got {len(atoms)}"

    # Centre the C3-C4 bond midpoint on the origin (the scan rotates about
    # this bond; the released asset additionally translates it to the cell
    # centre).
    mid = vscale(vadd(carbons[2], carbons[3]), 0.5)
    atoms = [(el, vsub(p, mid)) for el, p in atoms]

    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "hexane_idealized.xyz")
    with open(out, "w") as f:
        f.write(f"{len(atoms)}\n")
        f.write("idealized all-anti n-hexane (C-C 1.54 A, C-H 1.09 A, "
                "tetrahedral angles); C3-C4 midpoint at origin\n")
        for el, (x, y, z) in atoms:
            f.write(f"{el} {x: .10f} {y: .10f} {z: .10f}\n")
    print(f"wrote {out} ({len(atoms)} atoms)")


if __name__ == "__main__":
    main()

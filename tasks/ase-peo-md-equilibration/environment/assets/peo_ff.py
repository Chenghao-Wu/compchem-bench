"""Pinned minimalist force field for a single PEO chain (CompChemBench).

A toy polymer force field in ASE units (eV, Angstrom):

  - harmonic bonds:        E = 0.5 * BOND_K * (r - r0)^2
  - harmonic angles:       E = 0.5 * ANGLE_K * (theta - theta0)^2
  - non-bonded repulsion:  WCA (repulsive half of Lennard-Jones, cut and
                           shifted at r = 2^(1/6) * WCA_SIGMA)

Equilibrium bond lengths (r0) and angles (theta0) are frozen from the
construction geometry passed to ``make_calculator`` — i.e. the chain's own
MMFF94-optimized RDKit geometry defines the bonded reference. 1-2 (bonded)
and 1-3 (angle) atom pairs are excluded from the WCA term; all further
pairs (1-4 and beyond) feel only the short-range repulsion, so the model is
a self-avoiding harmonic chain — a standard implicit-good-solvent toy model
for a polymer coil.

The calculator is deterministic: pair lists are built once at construction
in a fixed order and all force accumulations use numpy vectorized ops over
those fixed arrays.

Units: energies eV, distances Angstrom, angles radians.
"""

import numpy as np
from ase.calculators.calculator import Calculator, all_changes

BOND_K = 25.0       # eV / Å^2
ANGLE_K = 0.5       # eV / rad^2  (flexible chain — conformational sampling)
WCA_EPSILON = 0.05  # eV
WCA_SIGMA = 2.5     # Å


def derive_angles(n_atoms, bonds):
    """All angle triplets (i, j, k) with j the central atom, from the bond
    list. Returned in a fixed sorted order."""
    neighbors = [[] for _ in range(n_atoms)]
    for i, j in bonds:
        neighbors[i].append(j)
        neighbors[j].append(i)
    angles = []
    for j in range(n_atoms):
        nbrs = sorted(neighbors[j])
        for a in range(len(nbrs)):
            for b in range(a + 1, len(nbrs)):
                angles.append((nbrs[a], j, nbrs[b]))
    return sorted(angles)


class PEOChainForceField(Calculator):
    implemented_properties = ["energy", "forces"]

    def __init__(self, bonds, r0, angles, theta0, pairs):
        super().__init__()
        self.bonds = np.asarray(bonds, dtype=int)      # (nb, 2)
        self.r0 = np.asarray(r0, dtype=float)          # (nb,)
        self.angles = np.asarray(angles, dtype=int)    # (na, 3)
        self.theta0 = np.asarray(theta0, dtype=float)  # (na,)
        self.pairs = np.asarray(pairs, dtype=int)      # (np, 2)
        self.rc = WCA_SIGMA * 2.0 ** (1.0 / 6.0)

    def calculate(self, atoms=None, properties=("energy", "forces"),
                  system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        pos = self.atoms.positions
        n = len(pos)
        energy = 0.0
        forces = np.zeros((n, 3))

        # ── harmonic bonds ──────────────────────────────────────────────
        i, j = self.bonds[:, 0], self.bonds[:, 1]
        d = pos[i] - pos[j]                      # (nb, 3)
        r = np.linalg.norm(d, axis=1)
        ehat = d / r[:, None]
        energy += float(0.5 * BOND_K * np.sum((r - self.r0) ** 2))
        f = (BOND_K * (r - self.r0))[:, None] * ehat   # on atom i, along -r_hat? see below
        # force on i is -dE/dr_i = -k(r-r0) * r_hat(i-j); on j it is +that
        np.add.at(forces, i, -f)
        np.add.at(forces, j, f)

        # ── harmonic angles ─────────────────────────────────────────────
        ai, aj, ak = self.angles[:, 0], self.angles[:, 1], self.angles[:, 2]
        v1 = pos[ai] - pos[aj]                   # j -> i
        v2 = pos[ak] - pos[aj]                   # j -> k
        n1 = np.linalg.norm(v1, axis=1)
        n2 = np.linalg.norm(v2, axis=1)
        cos = np.sum(v1 * v2, axis=1) / (n1 * n2)
        cos = np.clip(cos, -1.0, 1.0)
        theta = np.arccos(cos)
        sin = np.sqrt(np.maximum(1.0 - cos ** 2, 1e-12))
        energy += float(0.5 * ANGLE_K * np.sum((theta - self.theta0) ** 2))
        # d theta / d v1 and d theta / d v2 (standard angle-force form)
        dcos1 = v2 / (n1 * n2)[:, None] - (cos / n1 ** 2)[:, None] * v1
        dcos2 = v1 / (n1 * n2)[:, None] - (cos / n2 ** 2)[:, None] * v2
        dtheta1 = -dcos1 / sin[:, None]
        dtheta2 = -dcos2 / sin[:, None]
        coef = (ANGLE_K * (theta - self.theta0))[:, None]
        fi = -coef * dtheta1
        fk = -coef * dtheta2
        np.add.at(forces, ai, fi)
        np.add.at(forces, ak, fk)
        np.add.at(forces, aj, -(fi + fk))

        # ── WCA non-bonded repulsion ────────────────────────────────────
        pi, pj = self.pairs[:, 0], self.pairs[:, 1]
        d = pos[pi] - pos[pj]
        r = np.linalg.norm(d, axis=1)
        mask = r < self.rc
        if np.any(mask):
            rr = r[mask]
            dd = d[mask]
            sr = WCA_SIGMA / rr
            sr6 = sr ** 6
            sr12 = sr6 ** 2
            energy += float(np.sum(4.0 * WCA_EPSILON * (sr12 - sr6) + WCA_EPSILON))
            # |dE/dr| = 4 eps (12 sig^12/r^13 - 6 sig^6/r^7); force pushes apart
            fmag = 4.0 * WCA_EPSILON * (12.0 * sr12 / rr - 6.0 * sr6 / rr)
            f = (fmag / rr)[:, None] * dd      # on atom i, away from j
            ii = pi[mask]
            jj = pj[mask]
            np.add.at(forces, ii, f)
            np.add.at(forces, jj, -f)

        self.results["energy"] = energy
        self.results["forces"] = forces


def make_calculator(atoms, bonds):
    """Build the pinned PEO chain force field.

    atoms : ase.Atoms
        The construction (MMFF94-optimized) geometry. Equilibrium bond
        lengths and angles are frozen from THESE positions.
    bonds : sequence of (int, int)
        Covalent bonds (0-based atom indices), e.g. from the RDKit molecule.
    """
    n = len(atoms)
    bonds = sorted((min(int(a), int(b)), max(int(a), int(b))) for a, b in bonds)
    pos = atoms.get_positions()
    r0 = [float(np.linalg.norm(pos[a] - pos[b])) for a, b in bonds]
    angles = derive_angles(n, bonds)
    theta0 = []
    for a, b, c in angles:
        v1 = pos[a] - pos[b]
        v2 = pos[c] - pos[b]
        cos = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        theta0.append(float(np.arccos(np.clip(cos, -1.0, 1.0))))
    excluded = set(bonds)
    for a, b, c in angles:
        excluded.add((min(a, c), max(a, c)))
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
             if (i, j) not in excluded]
    return PEOChainForceField(bonds, r0, angles, theta0, pairs)

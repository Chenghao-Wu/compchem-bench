#!/usr/bin/env python3
"""Generate the relaxed endpoint assets for ase-neb-adatom.

Cu(100) 3x3 slab, 4 layers, 10 A vacuum, one adatom above a hollow site
(initial) and above the adjacent hollow site along x (final). Both are
relaxed with EMT to fmax < 0.01 eV/A. Run inside the task image.
"""
import numpy as np
from ase.build import fcc100
from ase.calculators.emt import EMT
from ase.optimize import BFGS
from ase.io import write

A = 3.615

slab = fcc100("Cu", size=(3, 3, 4), a=A, vacuum=10.0)
slab.calc = EMT()

# surface: top layer z
zs = slab.positions[:, 2]
z_top = zs.max()

# hollow site: center of a surface square. For fcc100 3x3 the surface atoms
# sit on a grid with spacing A/sqrt(2). Pick the hollow between four top
# atoms near the middle of the cell.
d = A / np.sqrt(2)  # surface nn spacing
# hollow site at (d, d) offset from a corner surface atom at (0,0)-ish;
# use (d/2, d/2) shift from the top-layer atom closest to origin
top = slab.positions[zs > z_top - 0.1]
x0 = top[:, 0].min()
y0 = top[:, 1].min()
ad_z = z_top + 1.9  # rough adatom height, relax will settle


def with_adatom(hx, hy):
    atoms = slab.copy()
    atoms.calc = EMT()
    atoms.append("Cu")
    atoms.positions[-1] = [hx, hy, ad_z]
    return atoms


h1 = (x0 + d / 2, y0 + d / 2)          # first hollow site
h2 = (x0 + 3 * d / 2, y0 + d / 2)      # adjacent hollow along x

for name, (hx, hy) in (("initial", h1), ("final", h2)):
    atoms = with_adatom(hx, hy)
    opt = BFGS(atoms, logfile=None)
    opt.run(fmax=0.01, steps=500)
    e = atoms.get_potential_energy()
    write(f"{name}.xyz", atoms, format="extxyz")
    fmax = float(np.max(np.linalg.norm(atoms.get_forces(), axis=1)))
    print(f"{name}: E={e:.8f} eV, fmax={fmax:.2e}, adatom z={atoms.positions[-1,2]:.4f}")

#!/usr/bin/env python3
"""
Authoring step 2: relax the idealized anti-hexane with pw.x and emit the
released asset `environment/assets/hexane_anti.xyz`, placed so the C3-C4 bond
midpoint is exactly at the centre of the 30-bohr cubic cell.

Runs INSIDE the task image (needs pw.x on PATH). Not used by the agent, the
oracle, or the verifier — it documents and reproduces the asset provenance
(see authoring/README.md).

Usage (inside the image, repo task dir mounted at /task):
    python3 /task/authoring/relax_and_emit_asset.py /task [start_xyz]

`start_xyz` defaults to authoring/hexane_idealized.xyz; passing a partially
relaxed xyz seeds BFGS from there instead (identical endpoint, fewer steps).
"""

import math
import os
import re
import subprocess
import sys
import tempfile

BOHR_TO_ANG = 0.529177210903   # CODATA 2018; fixed convention for the asset
CELLDM_BOHR = 30.0
BOX_ANG = CELLDM_BOHR * BOHR_TO_ANG
HALF = BOX_ANG / 2.0

RELAX_TEMPLATE = """&CONTROL
  calculation = 'relax'
  prefix = 'hexane_anti'
  outdir = './outdir'
  pseudo_dir = '{pseudo_dir}'
  forc_conv_thr = 1.0d-3
  etot_conv_thr = 1.0d-5
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
&IONS
/
ATOMIC_SPECIES
  C 12.0107 C.pbe-n-kjpaw_psl.1.0.0.UPF
  H 1.00794 H.pbe-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS angstrom
{positions}
K_POINTS gamma
"""


def read_xyz(path):
    lines = open(path).read().strip().splitlines()
    n = int(lines[0])
    atoms = []
    for line in lines[2:2 + n]:
        p = line.split()
        atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))
    return atoms


def main():
    task_dir = sys.argv[1]
    start = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        task_dir, "authoring", "hexane_idealized.xyz")
    ideal = read_xyz(start)
    pseudo_dir = os.path.join(task_dir, "environment", "assets", "pseudo")

    # translate so the C3-C4 midpoint (atoms 3 and 4, 1-based) sits at the
    # cell centre before relaxing
    c3 = ideal[2]
    c4 = ideal[3]
    mid = [(c3[i] + c4[i]) / 2.0 for i in (1, 2, 3)]
    shift = [HALF - m for m in mid]
    positions = "\n".join(
        f"  {el} {x + shift[0]:.10f} {y + shift[1]:.10f} {z + shift[2]:.10f}"
        for el, x, y, z in ideal
    )

    work = tempfile.mkdtemp(prefix="hexane_relax_")
    inp = RELAX_TEMPLATE.format(
        pseudo_dir=pseudo_dir, celldm=CELLDM_BOHR, positions=positions
    )
    with open(os.path.join(work, "relax.in"), "w") as f:
        f.write(inp)
    with open(os.path.join(work, "relax.out"), "w") as f:
        subprocess.run(["pw.x", "-in", "relax.in"], cwd=work, stdout=f,
                       stderr=subprocess.STDOUT, check=True, timeout=1800)
    content = open(os.path.join(work, "relax.out")).read()
    if "JOB DONE." not in content or "bfgs converged" not in content:
        raise RuntimeError("relax did not converge; see " + work)

    m = re.search(
        r"Begin final coordinates\s+ATOMIC_POSITIONS \(angstrom\)\s+"
        r"((?:\s*\w+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n)+)\s*End final coordinates",
        content)
    if not m:
        raise RuntimeError("no final ATOMIC_POSITIONS block")
    relaxed = []
    for line in m.group(1).strip().splitlines():
        p = line.split()
        relaxed.append((p[0], float(p[1]), float(p[2]), float(p[3])))

    # recentre: exact C3-C4 midpoint at the cell centre
    c3 = relaxed[2]
    c4 = relaxed[3]
    mid = [(c3[i] + c4[i]) / 2.0 for i in (1, 2, 3)]
    shift = [HALF - m for m in mid]
    out_path = os.path.join(task_dir, "environment", "assets", "hexane_anti.xyz")
    with open(out_path, "w") as f:
        f.write("20\n")
        f.write("n-hexane, all-anti conformer, pw.x PBE relax "
                "(ecutwfc=50 Ry, ecutrho=400 Ry, 30 bohr cubic cell); "
                "C3-C4 bond midpoint at cell centre; atom order C1..C6 then H\n")
        for el, x, y, z in relaxed:
            f.write(f"{el} {x + shift[0]:.10f} {y + shift[1]:.10f} {z + shift[2]:.10f}\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()

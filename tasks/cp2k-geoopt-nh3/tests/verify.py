#!/usr/bin/env python3
"""
Verifier for cp2k-geoopt-nh3:
  1. File existence + results.json schema (values/units)
  2. Output integrity (CP2K banner, GEOMETRY OPTIMIZATION COMPLETED)
  3. results.json sanity (geo_opt_converged, n_geo_steps)
  4. log <-> results consistency (last ENERGY| line)
  5. Numerical tolerance vs calibrated refs (energy, N-H bond)
  6. Trajectory structure check (xyz exists, NH3, N-H bond matches)
  7. REAL RECOMPUTE (cross-verify): the verifier builds a single-point
     CP2K input from the agent's final geometry (same method/basis/
     pseudopotential as the task input), runs it with the in-image CP2K,
     and requires three-way agreement:
         energy(agent log) == energy(results.json) == energy(recompute)
     Missing/abnormal structure or any recompute failure is a hard fail —
     there is no skip/warning path.
"""
import json
import sys
import os
import re
import shutil
import subprocess
import tempfile

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

ENERGY_RE = re.compile(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def last_energy(log_content):
    matches = ENERGY_RE.findall(log_content)
    if not matches:
        fail("No 'ENERGY| Total FORCE_EVAL' line found in CP2K output")
    return float(matches[-1])


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
check(os.path.isfile(os.path.join(WORKSPACE, "nh3_geoopt.out")), "Missing: nh3_geoopt.out")
check(os.path.isfile(os.path.join(WORKSPACE, "results.json")), "Missing: results.json")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "nh_bond_length", "geo_opt_converged", "n_geo_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "nh3_geoopt.out")) as f:
    content = f.read()

check("CP2K" in content, "nh3_geoopt.out missing CP2K banner")
check(
    "GEOMETRY OPTIMIZATION COMPLETED" in content,
    "nh3_geoopt.out missing 'GEOMETRY OPTIMIZATION COMPLETED' — optimization did not converge",
)

# ── Layer 3: results.json sanity ───────────────────────────────────────────────
check(values["geo_opt_converged"] is True, "geo_opt_converged must be true")
check(values["n_geo_steps"] >= 1, "n_geo_steps must be >= 1")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
energy_log = last_energy(content)
energy_rep = values["final_energy"]
nh_bond = values["nh_bond_length"]

check(
    abs(energy_log - energy_rep) <= refs["crossverify_energy_tol_Ha"],
    f"results.json energy {energy_rep:.10f} Ha != log energy {energy_log:.10f} Ha "
    f"(tol {refs['crossverify_energy_tol_Ha']:.1e})",
)

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
energy_ref = refs["final_energy_Ha_ref"]
energy_tol = refs["final_energy_Ha_tol"]
nh_bond_ref = refs["nh_bond_A_ref"]
nh_bond_tol = refs["nh_bond_A_tol"]

check(
    abs(energy_rep - energy_ref) <= energy_tol,
    f"final_energy={energy_rep:.8f} Ha differs from ref {energy_ref:.8f} Ha by >{energy_tol:.2e}",
)
check(
    abs(nh_bond - nh_bond_ref) <= nh_bond_tol,
    f"nh_bond_length={nh_bond:.4f} Å differs from ref {nh_bond_ref:.4f} Å by >{nh_bond_tol:.4f}",
)

# Sanity range for N-H bond
check(0.9 <= nh_bond <= 1.2, f"N-H bond {nh_bond:.4f} Å outside plausible range [0.9, 1.2]")

# ── Layer 6: Trajectory structure (required — hard fail if missing) ───────────
import numpy as np
from ase.io import read
from ase import Atoms as AseAtoms
from typing import List as TList

xyz_file = os.path.join(WORKSPACE, "nh3_geoopt-pos-1.xyz")
check(os.path.isfile(xyz_file),
      "Missing nh3_geoopt-pos-1.xyz — the CP2K geometry trajectory is required")

traj: TList[AseAtoms] = read(xyz_file, index=":")  # type: ignore[assignment]
check(len(traj) >= 2, f"xyz trajectory has {len(traj)} frame(s); expected >= 2")
last: AseAtoms = traj[-1]
check(len(last) == 4, f"Final frame has {len(last)} atoms (expected 4: NH3)")
symbols = sorted(last.get_chemical_symbols())
check(symbols == ["H", "H", "H", "N"], f"Expected N+3H, got {symbols}")

n_pos = last.positions[last.get_chemical_symbols().index("N")]
h_pos = last.positions[last.get_chemical_symbols().index("H")]
cv_nh = float(np.linalg.norm(h_pos - n_pos))
cv_nh_tol = refs.get("crossverify_nh_tol_A", 0.005)
check(
    abs(cv_nh - nh_bond) <= cv_nh_tol,
    f"Cross-verify N-H: xyz={cv_nh:.4f} Å vs results.json {nh_bond:.4f} Å (tol {cv_nh_tol})",
)

# ── Layer 7: REAL RECOMPUTE — single point on the agent's final geometry ──────
coord_lines = "\n".join(
    f"      {sym}   {pos[0]:.10f}   {pos[1]:.10f}   {pos[2]:.10f}"
    for sym, pos in zip(last.get_chemical_symbols(), last.positions)
)

sp_input = f"""&GLOBAL
  PROJECT crossverify_sp
  RUN_TYPE ENERGY
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 300
      REL_CUTOFF 60
    &END MGRID
    &QS
      EPS_DEFAULT 1.0E-12
    &END QS
    &SCF
      SCF_GUESS ATOMIC
      EPS_SCF 1.0E-7
      MAX_SCF 50
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
      PERIODIC NONE
    &END CELL
    &COORD
{coord_lines}
    &END COORD
    &KIND N
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q5
    &END KIND
    &KIND H
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q1
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "sp.inp"), "w") as f:
        f.write(sp_input)
    for data_file in ("BASIS_MOLOPT", "GTH_POTENTIALS"):
        os.symlink(os.path.join("/opt/cp2k/data", data_file),
                   os.path.join(tmpdir, data_file))

    env = dict(os.environ, OMP_NUM_THREADS="2")
    proc = subprocess.run(
        ["mpirun", "-np", "1", "cp2k", "-i", "sp.inp", "-o", "sp.out"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=600,
    )
    check(proc.returncode == 0,
          f"Cross-verify recompute: CP2K exited with code {proc.returncode}\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

    with open(os.path.join(tmpdir, "sp.out")) as f:
        sp_content = f.read()
    check("PROGRAM ENDED AT" in sp_content,
          "Cross-verify recompute: CP2K did not terminate normally")

    energy_re = last_energy(sp_content)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ha"]
check(
    abs(energy_re - energy_log) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != agent log {energy_log:.10f} Ha "
    f"(tol {cv_tol:.1e}) — log does not correspond to the final trajectory geometry",
)
check(
    abs(energy_re - energy_rep) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != results.json {energy_rep:.10f} Ha "
    f"(tol {cv_tol:.1e})",
)

print("PASS: cp2k-geoopt-nh3")

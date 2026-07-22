#!/usr/bin/env python3
"""
Verifier for cp2k-cell-opt-nacl:
  1. File existence + results.json schema (values/units)
  2. Output integrity (CP2K banner, GEOMETRY OPTIMIZATION COMPLETED)
  3. results.json sanity (cell_opt_converged, n_opt_steps)
  4. log <-> results consistency (last ENERGY| line, last CELL| |a|)
  5. Numerical tolerance vs calibrated refs (energy, a0)
  6. Trajectory structure check (xyz exists, 8 atoms, 4 Na + 4 Cl)
  7. REAL RECOMPUTE (cross-verify): the verifier builds a single-point
     CP2K input from the agent's final trajectory geometry and the final
     cell taken from the agent's log (same method/basis/pseudopotential
     as the task input), runs it with the in-image CP2K, and requires
     three-way agreement:
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
CELL_A_RE = re.compile(r"CELL\| Vector a \[angstrom\]:.*?\|a\| =\s*([\d.]+)")


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
for fname in ("nacl_cellopt.out", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "lattice_constant", "cell_opt_converged", "n_opt_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "nacl_cellopt.out")) as f:
    content = f.read()

check("CP2K" in content, "nacl_cellopt.out missing CP2K banner")
check(
    "GEOMETRY OPTIMIZATION COMPLETED" in content,
    "nacl_cellopt.out missing 'GEOMETRY OPTIMIZATION COMPLETED' — optimization did not converge",
)

# ── Layer 3: results.json sanity ───────────────────────────────────────────────
check(values["cell_opt_converged"] is True, "cell_opt_converged must be true")
check(values["n_opt_steps"] >= 1, "n_opt_steps must be >= 1")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
energy_log = last_energy(content)
energy_rep = values["final_energy"]
a0_rep = values["lattice_constant"]

check(
    abs(energy_log - energy_rep) <= refs["crossverify_energy_tol_Ha"],
    f"results.json energy {energy_rep:.10f} Ha != log energy {energy_log:.10f} Ha "
    f"(tol {refs['crossverify_energy_tol_Ha']:.1e})",
)

a_matches = CELL_A_RE.findall(content)
check(a_matches, "No 'CELL| Vector a' line found in CP2K output")
a0_log = float(a_matches[-1])
check(
    abs(a0_log - a0_rep) <= refs["consistency_a0_tol_A"],
    f"results.json a0 {a0_rep:.6f} Å != log a0 {a0_log:.6f} Å "
    f"(tol {refs['consistency_a0_tol_A']})",
)

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
check(
    abs(energy_rep - refs["final_energy_Ha_ref"]) <= refs["final_energy_Ha_tol"],
    f"final_energy={energy_rep:.8f} Ha differs from ref "
    f"{refs['final_energy_Ha_ref']:.8f} Ha by >{refs['final_energy_Ha_tol']:.2e}",
)
check(
    abs(a0_rep - refs["lattice_constant_A_ref"]) <= refs["lattice_constant_A_tol"],
    f"lattice_constant={a0_rep:.6f} Å differs from ref "
    f"{refs['lattice_constant_A_ref']:.6f} Å by >{refs['lattice_constant_A_tol']}",
)
check(5.5 <= a0_rep <= 6.1, f"a0 {a0_rep:.4f} Å outside plausible range for NaCl")

# ── Layer 6: Trajectory structure (required — hard fail if missing) ───────────
from ase.io import read

xyz_file = os.path.join(WORKSPACE, "nacl_cellopt-pos-1.xyz")
check(os.path.isfile(xyz_file),
      "Missing nacl_cellopt-pos-1.xyz — the CP2K geometry trajectory is required")

traj = read(xyz_file, index=":")
check(len(traj) >= 2, f"xyz trajectory has {len(traj)} frame(s); expected >= 2")
last = traj[-1]
check(len(last) == 8, f"Final frame has {len(last)} atoms (expected 8: 4 Na + 4 Cl)")
symbols = sorted(last.get_chemical_symbols())
check(symbols == ["Cl", "Cl", "Cl", "Cl", "Na", "Na", "Na", "Na"],
      f"Expected 4 Na + 4 Cl, got {symbols}")

# ── Layer 7: REAL RECOMPUTE — single point on the agent's final state ─────────
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
      ABC {a0_log:.6f} {a0_log:.6f} {a0_log:.6f}
    &END CELL
    &COORD
{coord_lines}
    &END COORD
    &KIND Na
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q9
    &END KIND
    &KIND Cl
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q7
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
    f"(tol {cv_tol:.1e}) — log does not correspond to the final trajectory state",
)
check(
    abs(energy_re - energy_rep) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != results.json {energy_rep:.10f} Ha "
    f"(tol {cv_tol:.1e})",
)

print("PASS: cp2k-cell-opt-nacl")

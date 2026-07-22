#!/usr/bin/env python3
"""
Verifier for cp2k-aimd-water:
  1. File existence + results.json schema (values/units)
  2. Output integrity (CP2K banner, normal termination)
  3. .ener integrity: exactly 21 data rows (steps 0..20, 0.5 fs spacing),
     Cons Qty == Kin + Pot per row, conserved-quantity drift below threshold
  4. log <-> results consistency (all reported quantities re-derived from
     the agent's .ener file)
  5. Numerical tolerance vs calibrated refs (final potential, mean temp)
  6. Trajectory structure check (xyz 21 frames, H2O)
  7. REAL RECOMPUTE (cross-verify): single-point CP2K on the final frame
     of the agent's position trajectory; requires three-way agreement:
         Pot(.ener last row) == final_potential(results.json) == energy(recompute)
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


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("h2o_aimd.out", "h2o_aimd-1.ener", "h2o_aimd-pos-1.xyz", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_potential", "mean_temperature", "cons_qty_drift", "n_md_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "h2o_aimd.out")) as f:
    content = f.read()

check("CP2K" in content, "h2o_aimd.out missing CP2K banner")
check("PROGRAM ENDED AT" in content,
      "h2o_aimd.out missing normal-termination footer 'PROGRAM ENDED AT'")

# ── Layer 3: .ener integrity ───────────────────────────────────────────────────
rows = []
with open(os.path.join(WORKSPACE, "h2o_aimd-1.ener")) as f:
    for line in f:
        if line.startswith("#"):
            continue
        p = line.split()
        check(len(p) >= 6, f"Malformed .ener row: {line!r}")
        rows.append((int(p[0]), float(p[1]), float(p[2]), float(p[3]),
                     float(p[4]), float(p[5])))

check(len(rows) == refs["expected_ener_rows"],
      f".ener has {len(rows)} data rows; expected exactly "
      f"{refs['expected_ener_rows']} (steps 0..20)")
check(rows[0][0] == 0 and rows[-1][0] == 20,
      f".ener steps run {rows[0][0]}..{rows[-1][0]}; expected 0..20")
for i, r in enumerate(rows):
    check(r[0] == i, f".ener row {i} has step {r[0]}; expected {i}")
    check(abs(r[1] - 0.5 * i) < 1e-6,
          f".ener row {i} time {r[1]} fs; expected {0.5 * i} fs")
    check(abs(r[5] - (r[2] + r[4])) <= refs["cons_kin_pot_tol_Ha"],
          f".ener row {i}: Cons Qty {r[5]:.9f} != Kin+Pot {r[2] + r[4]:.9f} "
          f"(tol {refs['cons_kin_pot_tol_Ha']:.1e}) — file not from a real NVE run")

drift = abs(rows[-1][5] - rows[0][5])
check(drift <= refs["drift_threshold_Ha"],
      f"Conserved-quantity drift {drift:.3e} Ha exceeds threshold "
      f"{refs['drift_threshold_Ha']:.1e} Ha — NVE integration not conservative")

# ── Layer 4: .ener <-> results consistency ─────────────────────────────────────
final_pot = rows[-1][4]
mean_temp = sum(r[3] for r in rows) / len(rows)

check(values["n_md_steps"] == 20, f"n_md_steps must be 20, got {values['n_md_steps']}")
check(abs(values["final_potential"] - final_pot) <= refs["consistency_pot_tol_Ha"],
      f"results.json final_potential {values['final_potential']:.9f} != .ener "
      f"last-row Pot {final_pot:.9f} (tol {refs['consistency_pot_tol_Ha']:.1e})")
check(abs(values["mean_temperature"] - mean_temp) <= refs["consistency_temp_tol_K"],
      f"results.json mean_temperature {values['mean_temperature']:.4f} != .ener "
      f"mean {mean_temp:.4f} (tol {refs['consistency_temp_tol_K']})")
check(abs(values["cons_qty_drift"] - drift) <= refs["consistency_drift_tol_Ha"],
      f"results.json cons_qty_drift {values['cons_qty_drift']:.3e} != .ener "
      f"drift {drift:.3e} (tol {refs['consistency_drift_tol_Ha']:.1e})")

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
check(abs(final_pot - refs["final_potential_Ha_ref"]) <= refs["final_potential_Ha_tol"],
      f"final_potential={final_pot:.9f} Ha differs from ref "
      f"{refs['final_potential_Ha_ref']:.9f} Ha by >{refs['final_potential_Ha_tol']:.1e}")
check(abs(mean_temp - refs["mean_temperature_K_ref"]) <= refs["mean_temperature_K_tol"],
      f"mean_temperature={mean_temp:.4f} K differs from ref "
      f"{refs['mean_temperature_K_ref']:.4f} K by >{refs['mean_temperature_K_tol']}")

# ── Layer 6: Trajectory structure (required — hard fail if missing) ───────────
from ase.io import read

traj = read(os.path.join(WORKSPACE, "h2o_aimd-pos-1.xyz"), index=":")
check(len(traj) == refs["expected_xyz_frames"],
      f"xyz trajectory has {len(traj)} frames; expected {refs['expected_xyz_frames']}")
last = traj[-1]
check(len(last) == 3, f"Final frame has {len(last)} atoms (expected 3: H2O)")
symbols = sorted(last.get_chemical_symbols())
check(symbols == ["H", "H", "O"], f"Expected O+2H, got {symbols}")

# ── Layer 7: REAL RECOMPUTE — single point on the agent's final frame ─────────
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
    &KIND O
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q6
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

    matches = ENERGY_RE.findall(sp_content)
    check(matches, "Cross-verify recompute: no ENERGY| line in output")
    energy_re = float(matches[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ha"]
check(
    abs(energy_re - final_pot) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != .ener last-row Pot "
    f"{final_pot:.10f} Ha (tol {cv_tol:.1e}) — trajectory does not correspond "
    f"to the reported energies",
)
check(
    abs(energy_re - values["final_potential"]) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != results.json "
    f"{values['final_potential']:.10f} Ha (tol {cv_tol:.1e})",
)

print("PASS: cp2k-aimd-water")

#!/usr/bin/env python3
"""
Verifier for ase-eos-cu:
  1. File existence + results.json schema (values/units)
  2. CSV integrity (7 rows, monotone volumes, plausible energies)
  3. Numerical tolerance on V0 and B0 vs calibrated refs
  4. REAL RECOMPUTE (cross-verify):
     a. rebuild every structure from the CSV lattice constants and
        recompute its energy with the pinned EMT calculator — each CSV
        energy must match the recomputed value (fabricated E-V curves
        fail here, even if they fit a perfect Birch-Murnaghan);
     b. refit the EOS from the recomputed data and require agreement
        with results.json.
  Any recompute failure is a hard fail.
"""
import json
import sys
import os

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("eos_data.csv", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("V0", "E0", "B0", "n_points"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

check(values["n_points"] == 7, f"n_points must be 7, got {values['n_points']}")

# ── Layer 2: CSV integrity ─────────────────────────────────────────────────────
rows_raw = []
with open(os.path.join(WORKSPACE, "eos_data.csv")) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        check(len(parts) == 3, f"eos_data.csv row has {len(parts)} columns (expected 3): {line!r}")
        try:
            row_a, row_v, row_e = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError as exc:
            fail(f"eos_data.csv non-numeric row: {line!r} — {exc}")
        rows_raw.append((row_a, row_v, row_e))

check(len(rows_raw) == 7, f"eos_data.csv has {len(rows_raw)} rows (expected 7)")

a_vals = [r[0] for r in rows_raw]
volumes = [r[1] for r in rows_raw]
energies = [r[2] for r in rows_raw]

# Volumes must be monotonically increasing (a from 3.5→3.7)
for i in range(1, len(volumes)):
    check(volumes[i] > volumes[i - 1], f"eos_data.csv volumes not monotonically increasing at row {i}")

# Volumes must be consistent with the lattice constants (V = a^3/4 for fcc primitive cell)
for i, (a, v, _) in enumerate(rows_raw):
    v_expected = a ** 3 / 4.0
    check(abs(v - v_expected) <= 0.01,
          f"eos_data.csv row {i}: V={v:.4f} Å³ inconsistent with a={a:.4f} Å (a³/4={v_expected:.4f})")

# Energies must be in a physically plausible range for an EMT Cu fcc unit cell
for i, e in enumerate(energies):
    check(-5.0 <= e <= 5.0, f"eos_data.csv energy {e:.4f} eV at row {i} outside [-5, 5] eV")

# ── Layer 3: Numerical tolerance ───────────────────────────────────────────────
v0 = values["V0"]
b0 = values["B0"]

v0_ref = refs["V0_A3_ref"]
b0_ref = refs["B0_GPa_ref"]
v0_tol = refs["V0_tol_percent"] / 100.0
b0_tol = refs["B0_tol_percent"] / 100.0

check(
    abs(v0 - v0_ref) / v0_ref <= v0_tol,
    f"V0={v0:.4f} Å³ differs from ref {v0_ref:.4f} Å³ by >{refs['V0_tol_percent']}%",
)
check(
    abs(b0 - b0_ref) / b0_ref <= b0_tol,
    f"B0={b0:.2f} GPa differs from ref {b0_ref:.2f} GPa by >{refs['B0_tol_percent']}%",
)

# ── Layer 4a: REAL RECOMPUTE — EMT energy of every CSV structure ─────────────
from ase.build import bulk
from ase.calculators.emt import EMT

e_tol = refs["crossverify_energy_tol_eV"]
recomputed_energies = []
for i, (a, v, e_csv) in enumerate(rows_raw):
    cu = bulk("Cu", "fcc", a=a)
    check(abs(cu.get_volume() - v) <= 0.01,
          f"eos_data.csv row {i}: rebuilt volume {cu.get_volume():.4f} != CSV {v:.4f}")
    cu.calc = EMT()
    e_re = float(cu.get_potential_energy())
    recomputed_energies.append(e_re)
    check(
        abs(e_re - e_csv) <= e_tol,
        f"Cross-verify point {i} (a={a:.4f} Å): recomputed EMT energy {e_re:.6f} eV "
        f"!= CSV {e_csv:.6f} eV (tol {e_tol}) — CSV energies are not real EMT results",
    )

# ── Layer 4b: Cross-verify — refit EOS from the recomputed data ───────────────
from ase.eos import EquationOfState
eos = EquationOfState(volumes, recomputed_energies, eos="birchmurnaghan")
v0_cv, e0_cv, b0_cv_eV = eos.fit()
b0_cv_GPa = b0_cv_eV * 160.21766

cv_v_tol = refs.get("crossverify_V0_tol_A3", 0.5)
cv_b_tol = refs.get("crossverify_B0_tol_GPa", 10.0)
check(
    abs(v0_cv - v0) <= cv_v_tol,
    f"Cross-verify V0: refit {v0_cv:.4f} vs reported {v0:.4f} Å³ (tol {cv_v_tol})",
)
check(
    abs(b0_cv_GPa - b0) <= cv_b_tol,
    f"Cross-verify B0: refit {b0_cv_GPa:.2f} vs reported {b0:.2f} GPa (tol {cv_b_tol})",
)

print("PASS: ase-eos-cu")

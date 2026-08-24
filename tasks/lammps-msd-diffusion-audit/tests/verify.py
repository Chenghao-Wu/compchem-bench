#!/usr/bin/env python3
"""
Verifier for lammps-msd-diffusion-audit.

  1. File existence + results.json values/units schema
  2. Asset integrity: sha256 of every pinned asset under /workspace/assets
     must match refs.json "asset_hashes" (the evidence files — msd.dat,
     in.lammps, log.lammps, README.md, analyze_msd.py — are pinned; the
     colleague's derived outputs diffusion_summary.txt / msd_analysis.png
     are deliberately NOT pinned, because rerunning the colleague's script
     is a legitimate audit step and it overwrites both)
  3. Independent re-fit of the hash-verified msd.dat: time axis from the
     timestep command in the hash-verified in.lammps; closed 50-100 ps
     window; straight-line fit with intercept; D = slope/6 in 3D
  4. Decoy guards with specific messages:
     (a) D == the colleague's 1.7124e-4 cm^2/s (slope/2 over 100-500 ps)
     (b) D == 5.708e-5 cm^2/s (right factor, but the colleague's 100-500 ps
         window instead of the requested 50-100 ps)
  5. Numeric agreement of results.json with the verifier's own fit
     (D, slope, R^2, n_fit_points)
  6. audit.json: three verdicts exact, identified_errors exact set
  7. audit.md present and non-trivial

All reference numbers are derived from the data at verify time; refs.json
carries only tolerances, the expected verdicts, and asset hashes.
"""
import hashlib
import json
import os
import re
import sys

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"
ASSETS = os.path.join(WORKSPACE, "assets")

RESULT_KEYS = ("D_cm2_s", "slope_A2_per_ps", "r_squared", "n_fit_points")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: files + results.json schema ──────────────────────────────────────
for fname in ("results.json", "audit.json", "audit.md"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in RESULT_KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
    check(isinstance(values[key], (int, float)) and not isinstance(values[key], bool),
          f"results.json values[{key!r}] must be numeric")

# ── Layer 2: asset integrity (sha256 pins) ────────────────────────────────────
for rel, digest in refs["asset_hashes"].items():
    path = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(path), f"asset missing from /workspace: {rel}")
    got = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
    check(got == digest,
          f"{rel} was modified (sha256 mismatch) — do not edit the assets; "
          f"the audit must be reproducible from the delivered package")

# ── Layer 3: independent re-fit of the hash-verified data ─────────────────────
with open(os.path.join(ASSETS, "in.lammps")) as f:
    inp = f.read()
check(re.search(r"^\s*units\s+real\b", inp, re.MULTILINE),
      "assets/in.lammps: expected 'units real'")
m = re.search(r"^\s*timestep\s+([\d.eE+]+)", inp, re.MULTILINE)
check(m is not None, "assets/in.lammps: no timestep command found")
dt_ps = float(m.group(1)) / 1000.0  # real units -> fs; convert to ps

data = np.loadtxt(os.path.join(ASSETS, "msd.dat"))
step, mx, my, mz, mt = data.T
t = step * dt_ps

LO, HI = refs["fit_window_ps"]
sel = (t >= LO) & (t <= HI)
n_ref = int(sel.sum())
check(n_ref == refs["n_fit_points_expected"],
      f"verifier self-fit found {n_ref} samples in [{LO}, {HI}] ps "
      f"(expected {refs['n_fit_points_expected']}) — asset data inconsistent")

def fit(tt, yy):
    slope, intercept = np.polyfit(tt, yy, 1)
    resid = yy - (slope * tt + intercept)
    r2 = 1 - np.sum(resid**2) / np.sum((yy - yy.mean())**2)
    return slope, intercept, r2

slope_ref, ic_ref, r2_ref = fit(t[sel], mt[sel])
D_ref = slope_ref / 6.0 * 1e-4                       # 3D Einstein: MSD = 6 D t

# Decoy values, derived from the same data the way a flawed audit would:
sel_c = (t >= 100.0) & (t <= 500.0)
D_colleague = fit(t[sel_c], mt[sel_c])[0] / 2.0 * 1e-4   # wrong factor AND window
D_wrong_window = fit(t[sel_c], mt[sel_c])[0] / 6.0 * 1e-4  # right factor, wrong window

# ── Layer 4: decoy guards (specific messages before the band check) ───────────
D_agent = float(values["D_cm2_s"])
gtol = refs["decoy_guard_tol_frac"]
check(abs(D_agent - D_colleague) > gtol * D_colleague,
      f"D = {D_agent:.4e} cm^2/s reproduces the colleague's erroneous value "
      f"({D_colleague:.4e}) — that number applies slope/2 to the TOTAL 3D MSD "
      f"(the 3D Einstein relation is MSD = 6 D t) and comes from the wrong "
      f"fit window")
check(abs(D_agent - D_wrong_window) > gtol * D_wrong_window,
      f"D = {D_agent:.4e} cm^2/s matches a correct-factor fit over the "
      f"colleague's 100-500 ps window ({D_wrong_window:.4e}) — the requested "
      f"window is 50-100 ps")

# ── Layer 5: numeric agreement with the verifier's fit ────────────────────────
def close(got, ref, frac, what):
    check(abs(float(got) - ref) <= frac * abs(ref),
          f"{what}: got {float(got):.6g}, verifier's independent fit gives "
          f"{ref:.6g} (tolerance {frac*100:.0f}%)")

close(D_agent, D_ref, refs["D_tol_frac"], "D_cm2_s (50-100 ps, D = slope/6)")
close(values["slope_A2_per_ps"], slope_ref, refs["slope_tol_frac"],
      "slope_A2_per_ps")
check(abs(float(values["r_squared"]) - r2_ref) <= refs["r2_tol_abs"],
      f"r_squared: got {float(values['r_squared']):.6f}, verifier's fit gives "
      f"{r2_ref:.6f} (tolerance ±{refs['r2_tol_abs']})")
n_lo, n_hi = refs["n_fit_points_agent_range"]
check(n_lo <= int(values["n_fit_points"]) <= n_hi,
      f"n_fit_points: got {values['n_fit_points']}, expected ~{n_ref} samples "
      f"in the 50-100 ps interval at 0.5 ps spacing (accepted {n_lo}-{n_hi})")

# ── Layer 6: audit.json verdicts ──────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "audit.json")) as f:
    audit = json.load(f)

for key, want in refs["expected_verdicts"].items():
    check(key in audit, f"audit.json missing key: {key}")
    check(audit[key] is want,
          f"audit.json {key}: got {audit[key]!r}, expected {want!r}")

check("identified_errors" in audit, "audit.json missing key: identified_errors")
errs = audit["identified_errors"]
check(isinstance(errs, list) and all(isinstance(e, str) for e in errs),
      "audit.json identified_errors must be a list of strings")
unknown = set(errs) - set(refs["allowed_error_vocab"])
check(not unknown,
      f"audit.json identified_errors contains values outside the allowed "
      f"vocabulary: {sorted(unknown)}")
want_errs = set(refs["expected_errors"])
got_errs = set(errs)
check(len(errs) == len(got_errs), "identified_errors contains duplicates")
check(want_errs <= got_errs,
      f"audit missed real error(s): {sorted(want_errs - got_errs)}")
check(got_errs <= want_errs,
      f"audit claims error(s) that are not present: {sorted(got_errs - want_errs)}")

# ── Layer 7: audit.md ─────────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "audit.md")) as f:
    report = f.read()
check(len(report) >= refs["audit_min_chars"],
      f"audit.md too short ({len(report)} chars < {refs['audit_min_chars']}) — "
      f"document the evidence for each verdict")

print("PASS: lammps-msd-diffusion-audit")

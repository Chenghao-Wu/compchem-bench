#!/usr/bin/env python3
"""
Verifier for lammps-msd-diffusion:
  1. File existence + results.json schema (values/units)
  2. Log integrity: banner, completion footer, exactly two run segments
     (equil 2000-step, production 10000-step) with the expected row counts
  3. MSD series sanity: 101 production rows, MSD(0)=0, non-decreasing tail
  4. Numerical tolerance: D within +/-15% of the calibrated reference
  5. Consistency: verifier re-fits D from the log's MSD column over the
     mandated window (steps >= 7000) — must match results.json
  6. L4 REAL RECOMPUTE: parse traj.dump (unwrapped coordinates), recompute
     MSD(t) independently from the first production frame, verify the final
     MSD matches the log, and fit D over the same window — must match
     results.json. A fabricated dump or a fabricated MSD column fails here.
"""
import json
import sys
import os
import re

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

DT = 0.005
PROD_START = 2000
FIT_FROM = 7000
N_ATOMS = 864


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("log.lammps", "traj.dump", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("diffusion_D", "n_msd_rows"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

D_agent = float(values["diffusion_D"])

# ── Layer 2: Log integrity (two segments) ─────────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Total wall time" in log_content,
      "log.lammps missing 'Total wall time' — run incomplete")

segments = []
cur = None
for line in log_content.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        cur = []
        segments.append(cur)
        continue
    if cur is not None and re.match(r"^\d+\s+[-\d.eE+]+", s):
        cur.append(s)
    if "Loop time" in line:
        cur = None

expected_segs = refs["expected_thermo_segments"]
check(len(segments) == len(expected_segs),
      f"Expected {len(expected_segs)} run segments (equilibration + production), "
      f"found {len(segments)}")
for i, (seg, expect) in enumerate(zip(segments, expected_segs)):
    check(len(seg) == expect["n_lines"],
          f"Run segment {i+1} has {len(seg)} thermo lines (expected {expect['n_lines']})")
    check(int(seg[0].split()[0]) == expect["first_step"] and
          int(seg[-1].split()[0]) == expect["last_step"],
          f"Run segment {i+1} covers steps {seg[0].split()[0]}..{seg[-1].split()[0]} "
          f"(expected {expect['first_step']}..{expect['last_step']})")

prod = segments[-1]
steps = np.array([float(l.split()[0]) for l in prod])
msd_log = np.array([float(l.split()[3]) for l in prod])

# ── Layer 3: MSD series sanity ─────────────────────────────────────────────────
check(values["n_msd_rows"] == len(prod),
      f"results.json n_msd_rows={values['n_msd_rows']} != log production rows {len(prod)}")
check(abs(msd_log[0]) < 1e-6, f"MSD at production start must be 0, got {msd_log[0]}")
check(all(m >= 0.0 for m in msd_log), "MSD contains negative values")
# The diffusive tail must be increasing on average: last 25% mean > first 25% mean
q = len(msd_log) // 4
check(msd_log[-q:].mean() > msd_log[:q].mean(),
      "MSD is not increasing — not a diffusive trajectory")

# ── Layer 4: Numerical tolerance on D ──────────────────────────────────────────
D_ref, D_tol_frac = refs["diffusion_D_ref"], refs["diffusion_D_tol_frac"]
check(abs(D_agent - D_ref) / D_ref <= D_tol_frac,
      f"diffusion_D={D_agent:.5f} differs from ref {D_ref:.5f} by "
      f">{D_tol_frac*100:.0f}%")

# ── Layer 5: Consistency — refit D from the log's MSD column ──────────────────
def fit_D(step_arr, msd_arr):
    mask = step_arr >= FIT_FROM
    t = (step_arr[mask] - PROD_START) * DT
    slope, _ = np.polyfit(t, msd_arr[mask], 1)
    return slope / 6.0

D_logfit = fit_D(steps, msd_log)
check(abs(D_logfit - D_agent) / max(abs(D_agent), 1e-9) <= refs["consistency_D_tol_frac"],
      f"results.json D={D_agent:.5f} != verifier refit of the log MSD "
      f"{D_logfit:.5f} (tol {refs['consistency_D_tol_frac']*100:.0f}%)")

# ── Layer 6: L4 REAL RECOMPUTE — MSD from traj.dump ───────────────────────────
frames = []
with open(os.path.join(WORKSPACE, "traj.dump")) as f:
    lines = f.read().splitlines()

i = 0
while i < len(lines):
    check(lines[i].startswith("ITEM: TIMESTEP"),
          f"traj.dump: malformed frame header at line {i+1}")
    step = int(lines[i + 1])
    check(lines[i + 2].startswith("ITEM: NUMBER OF ATOMS"),
          f"traj.dump: missing NUMBER OF ATOMS at line {i+3}")
    n = int(lines[i + 3])
    check(n == N_ATOMS, f"traj.dump frame at step {step} has {n} atoms (expected {N_ATOMS})")
    check(lines[i + 4].startswith("ITEM: BOX BOUNDS"),
          f"traj.dump: missing BOX BOUNDS at line {i+5}")
    i += 5 + 3  # skip box bounds
    header = lines[i]
    check("ITEM: ATOMS" in header, f"traj.dump: missing ATOMS header at line {i+1}")
    cols = header.split()[2:]
    idi = cols.index("id")
    xi, yi, zi = cols.index("xu"), cols.index("yu"), cols.index("zu")
    ids = np.empty(n, dtype=int)
    pos = np.empty((n, 3))
    for k in range(n):
        p = lines[i + 1 + k].split()
        ids[k] = int(p[idi])
        pos[k] = (float(p[xi]), float(p[yi]), float(p[zi]))
    # LAMMPS may reorder atoms between frames (in-memory atom sorting);
    # sort by atom id so per-atom displacements line up across frames.
    order = np.argsort(ids)
    frames.append((step, pos[order]))
    i += 1 + n

check(len(frames) == refs["n_frames_expected"],
      f"traj.dump has {len(frames)} frames (expected {refs['n_frames_expected']} "
      f"— one per 100 production steps)")
dump_steps = np.array([fr[0] for fr in frames])
check(dump_steps[0] == PROD_START and dump_steps[-1] == 12000,
      f"traj.dump spans steps {dump_steps[0]}..{dump_steps[-1]} "
      f"(expected {PROD_START}..12000)")

# MSD relative to the first production frame (same origin as compute msd)
r0 = frames[0][1]
msd_dump = np.array([np.mean(np.sum((fr[1] - r0) ** 2, axis=1)) for fr in frames])

# Final-frame MSD must match the log's final MSD
check(abs(msd_dump[-1] - msd_log[-1]) / msd_log[-1] <= refs["l4_msd_tol_frac"],
      f"L4: dump-recomputed final MSD {msd_dump[-1]:.4f} != log MSD "
      f"{msd_log[-1]:.4f} (tol {refs['l4_msd_tol_frac']*100:.1f}%) — the "
      f"trajectory does not back the reported MSD")

# Fit D from the dump MSD over the same window
D_dump = fit_D(dump_steps, msd_dump)
check(abs(D_dump - D_agent) / max(abs(D_agent), 1e-9) <= refs["l4_D_tol_frac"],
      f"L4: dump-recomputed D={D_dump:.5f} != results.json D={D_agent:.5f} "
      f"(tol {refs['l4_D_tol_frac']*100:.0f}%) — reported D is not supported "
      f"by the trajectory")

print("PASS: lammps-msd-diffusion")

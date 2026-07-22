#!/usr/bin/env python3
"""
Verifier for lammps-nvt-rdf:
  1. File existence + results.json schema (values/units)
  2. Log integrity: LAMMPS banner, completion footer, and BOTH run
     segments present with the expected thermo row counts and step ranges
     (equilibration 0..2000, production 2000..5000)
  3. RDF data integrity: exactly 100 bins on the expected r grid
     (compute rdf 100, cutoff 2.5σ → bin centers (i-0.5)·0.025),
     non-negative g(r)
  4. final.data integrity: exists, exactly 500 atoms
  5. Numerical tolerance on peak position/height vs calibrated refs
  6. Cross-verify: re-find peak from rdf.dat, compare to results.json
  7. REAL RECOMPUTE: run a 0-step LAMMPS evaluation on final.data with the
     same pair settings and require the recomputed potential energy to
     match the log's last thermo line — proves final.data is a genuine
     product of the claimed run.
"""
import json
import sys
import os
import re
import subprocess
import tempfile

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
for fname in ("log.lammps", "rdf.dat", "final.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("first_peak_r", "first_peak_gr", "n_rdf_bins"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Log integrity (both run segments) ────────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Total wall time" in log_content, "log.lammps missing 'Total wall time' — run incomplete")

# Parse thermo segments (one per run command)
segments = []
cur = None
for line in log_content.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        cur = []
        segments.append(cur)
        continue
    if cur is not None and re.match(r"^\d+\s+[\d.eE+\-]+", s):
        cur.append(s)
    if "Loop time" in line:
        cur = None

expected_segs = refs["expected_thermo_segments"]
check(len(segments) == len(expected_segs),
      f"Expected {len(expected_segs)} run segments (equilibration + production), "
      f"found {len(segments)} — both runs must complete")

for i, (seg, expect) in enumerate(zip(segments, expected_segs)):
    check(len(seg) == expect["n_lines"],
          f"Run segment {i+1} has {len(seg)} thermo lines (expected {expect['n_lines']})")
    first_step = int(seg[0].split()[0])
    last_step = int(seg[-1].split()[0])
    check(first_step == expect["first_step"] and last_step == expect["last_step"],
          f"Run segment {i+1} covers steps {first_step}..{last_step} "
          f"(expected {expect['first_step']}..{expect['last_step']})")

last_thermo_pe = float(segments[-1][-1].split()[2])

# ── Layer 3: RDF data integrity ────────────────────────────────────────────────
r_vals = []
gr_vals = []
with open(os.path.join(WORKSPACE, "rdf.dat")) as f:
    for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            # ave/time block header line ("<timestep> <nrows>") — skip
            continue
        try:
            r_vals.append(float(parts[1]))
            gr_vals.append(float(parts[2]))
        except ValueError:
            continue

n_bins_expected = refs["n_rdf_bins_expected"]
check(len(r_vals) == n_bins_expected,
      f"rdf.dat has {len(r_vals)} data rows (expected exactly {n_bins_expected} — "
      f"compute rdf {n_bins_expected})")

# r grid must match the expected bin centers: (i-0.5) * cutoff/nbins
rmax = refs["rdf_cutoff"]
dr = rmax / n_bins_expected
for i, r in enumerate(r_vals, start=1):
    expected_r = (i - 0.5) * dr
    check(abs(r - expected_r) <= 1e-3,
          f"rdf.dat bin {i}: r={r:.5f} != expected bin center {expected_r:.5f} "
          f"(grid inconsistent with 'compute rdf {n_bins_expected}' up to {rmax}σ)")

check(all(g >= 0.0 for g in gr_vals), "rdf.dat contains negative g(r) values")

# ── Layer 4: final.data integrity ─────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "final.data")) as f:
    data_content = f.read()

atoms_match = re.search(r"^\s*(\d+)\s+atoms\s*$", data_content, re.MULTILINE)
check(atoms_match is not None, "final.data missing 'N atoms' header line")
check(int(atoms_match.group(1)) == refs["final_data_atoms"],
      f"final.data contains {atoms_match.group(1)} atoms (expected {refs['final_data_atoms']})")

# ── Layer 5: Numerical tolerance ───────────────────────────────────────────────
check(values["n_rdf_bins"] == n_bins_expected,
      f"results.json n_rdf_bins must be {n_bins_expected}, got {values['n_rdf_bins']}")

peak_r = values["first_peak_r"]
peak_gr = values["first_peak_gr"]

peak_r_ref = refs["first_peak_r_ref"]
peak_r_tol = refs["first_peak_r_tol"]
peak_gr_ref = refs["first_peak_gr_ref"]
peak_gr_tol_frac = refs["first_peak_gr_tol_frac"]

check(
    abs(peak_r - peak_r_ref) <= peak_r_tol,
    f"first_peak_r={peak_r:.3f} outside [{peak_r_ref - peak_r_tol:.3f}, "
    f"{peak_r_ref + peak_r_tol:.3f}] σ",
)
check(
    abs(peak_gr - peak_gr_ref) / peak_gr_ref <= peak_gr_tol_frac,
    f"first_peak_gr={peak_gr:.3f} differs from ref {peak_gr_ref:.3f} "
    f"by >{peak_gr_tol_frac*100:.0f}%",
)

# ── Layer 6: Cross-verify peak from rdf.dat ────────────────────────────────────
import numpy as np
r_arr = np.array(r_vals)
gr_arr = np.array(gr_vals)
mask = r_arr > 0.5
peak_idx = int(np.argmax(gr_arr[mask]))
cv_peak_r = float(r_arr[mask][peak_idx])
cv_peak_gr = float(gr_arr[mask][peak_idx])

cv_r_tol = refs.get("crossverify_r_tol", 0.1)
cv_gr_tol_frac = refs.get("crossverify_gr_tol_frac", 0.05)

check(
    abs(cv_peak_r - peak_r) <= cv_r_tol,
    f"Cross-verify: rdf.dat peak r={cv_peak_r:.3f} vs results.json {peak_r:.3f}",
)
check(
    abs(cv_peak_gr - peak_gr) / max(peak_gr, 0.1) <= cv_gr_tol_frac,
    f"Cross-verify: rdf.dat peak g(r)={cv_peak_gr:.3f} vs results.json {peak_gr:.3f}",
)

# ── Layer 7: REAL RECOMPUTE — 0-step PE evaluation of final.data ──────────────
recompute_input = """units           lj
atom_style      atomic
dimension       3
boundary        p p p
pair_style      lj/cut 2.5
read_data       final.data
mass            1 1.0
pair_coeff      1 1 1.0 1.0 2.5
neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no
thermo          1
thermo_style    custom step temp pe
run             0
"""

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
        f.write(recompute_input)
    with open(os.path.join(tmpdir, "final.data"), "w") as f:
        f.write(data_content)

    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["lmp_serial", "-in", "recompute.in"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=120,
    )
    check(proc.returncode == 0,
          f"Cross-verify recompute: LAMMPS exited with code {proc.returncode}\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

    re_thermo = re.findall(r"^\s*\d+\s+[\d.eE+\-]+\s+([\d.eE+\-]+)\s*$",
                           proc.stdout, re.MULTILINE)
    check(re_thermo, "Cross-verify recompute: no thermo output from 0-step run")
    re_pe = float(re_thermo[-1])
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

pe_tol = refs["crossverify_pe_tol"]
check(
    abs(re_pe - last_thermo_pe) <= pe_tol,
    f"Cross-verify: recomputed PE of final.data {re_pe:.6f} != log last thermo PE "
    f"{last_thermo_pe:.6f} (tol {pe_tol}) — final.data is not the genuine product "
    f"of the claimed run",
)

# Hidden anchor: the seed is pinned and the run length is fixed, so the final
# PE is a deterministic constant. This also kills the "run a shorter
# simulation and wrap it in a full-length log" vector.
check(
    abs(re_pe - refs["final_pe_ref"]) <= refs["final_pe_tol"],
    f"recomputed final PE {re_pe:.6f} differs from pinned ref "
    f"{refs['final_pe_ref']:.6f} by > {refs['final_pe_tol']} — the run that "
    f"produced final.data is not the pinned-seed, full-length reference run",
)

print("PASS: lammps-nvt-rdf")

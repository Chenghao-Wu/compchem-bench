#!/usr/bin/env python3
"""
Verifier for cp2k-h2o-sp:
  1. File existence + results.json schema (values/units)
  2. Output integrity (CP2K banner, PROGRAM ENDED AT marker, SCF iterations)
  3. results.json sanity (scf_converged, n_scf_steps)
  4. Numerical tolerance vs calibrated reference
  5. REAL RECOMPUTE (cross-verify): the verifier reruns the identical
     single-point itself (same input, same in-image CP2K binary) and
     requires three-way agreement:
         energy(agent log) == energy(results.json) == energy(recompute)
     Any anomaly (missing input, CP2K failure, unparseable output) is a
     hard fail — there is no skip/warning path.
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

# ── Layer 0: ASSET INTEGRITY — never trust the workspace copy ────────────────
# /workspace/assets is agent-writable; any asset this verifier relies on is
# pinned by sha256 in refs.json (P2 asset-integrity convention).
import hashlib

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

for rel_path, want_hash in refs.get("asset_hashes", {}).items():
    apath = os.path.join(WORKSPACE, rel_path)
    check(os.path.isfile(apath), f"pinned asset missing: {rel_path}")
    got_hash = _sha256(apath)
    check(got_hash == want_hash,
          f"asset {rel_path} was tampered with: sha256 {got_hash} != pinned {want_hash}")


# ── Layer 1: File existence + schema ───────────────────────────────────────────
check(os.path.isfile(os.path.join(WORKSPACE, "h2o_sp.out")), "Missing: h2o_sp.out")
check(os.path.isfile(os.path.join(WORKSPACE, "results.json")), "Missing: results.json")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "scf_converged", "n_scf_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "h2o_sp.out")) as f:
    content = f.read()

check("CP2K" in content, "h2o_sp.out missing CP2K version banner")
check("PROGRAM ENDED AT" in content,
      "h2o_sp.out missing normal termination marker 'PROGRAM ENDED AT'")

# Must have SCF iteration lines (proves calculation actually ran)
scf_lines = re.findall(r"^\s+\d+\s+[-\d.E+]+\s+[-\d.E+]+", content, re.MULTILINE)
min_scf = refs.get("min_scf_lines", 3)
check(len(scf_lines) >= min_scf,
      f"h2o_sp.out has only {len(scf_lines)} SCF iteration lines (expected >= {min_scf})")

# ── Layer 3: results.json sanity ───────────────────────────────────────────────
check(values["scf_converged"] is True, "scf_converged must be true")
check(values["n_scf_steps"] >= 1, "n_scf_steps must be >= 1")

# ── Layer 4: log <-> results consistency + reference tolerance ────────────────
energy_log = last_energy(content)
energy_rep = values["total_energy"]

check(
    abs(energy_log - energy_rep) <= refs["crossverify_energy_tol_Ha"],
    f"results.json energy {energy_rep:.10f} Ha != log energy {energy_log:.10f} Ha "
    f"(tol {refs['crossverify_energy_tol_Ha']:.1e})",
)

energy_ref = refs["total_energy_Ha_ref"]
energy_tol = refs["total_energy_Ha_tol"]
check(
    abs(energy_rep - energy_ref) <= energy_tol,
    f"total_energy={energy_rep:.8f} Ha differs from ref {energy_ref:.8f} Ha "
    f"by {abs(energy_rep - energy_ref):.2e} (tol={energy_tol:.2e})",
)

# Spot-check: energy must be in reasonable range for H2O PBE/DZVP (roughly -17 Ha)
check(
    -20.0 <= energy_rep <= -15.0,
    f"total_energy={energy_rep:.4f} Ha outside plausible range [-20, -15] for H2O/PBE/DZVP",
)

# ── Layer 5: REAL RECOMPUTE — verifier reruns the single-point itself ─────────
src_inp = os.path.join(WORKSPACE, "assets", "h2o_sp.inp")
check(os.path.isfile(src_inp),
      "assets/h2o_sp.inp missing from image — cannot recompute (image corrupted?)")

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    shutil.copy(src_inp, os.path.join(tmpdir, "h2o_sp.inp"))
    for data_file in ("BASIS_MOLOPT", "GTH_POTENTIALS"):
        os.symlink(os.path.join("/opt/cp2k/data", data_file),
                   os.path.join(tmpdir, data_file))

    env = dict(os.environ, OMP_NUM_THREADS="2")
    proc = subprocess.run(
        ["mpirun", "-np", "1", "cp2k", "-i", "h2o_sp.inp", "-o", "recompute.out"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=600,
    )
    check(proc.returncode == 0,
          f"Cross-verify recompute: CP2K exited with code {proc.returncode}\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

    with open(os.path.join(tmpdir, "recompute.out")) as f:
        recompute_content = f.read()
    check("PROGRAM ENDED AT" in recompute_content,
          "Cross-verify recompute: CP2K did not terminate normally")

    energy_re = last_energy(recompute_content)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ha"]
check(
    abs(energy_re - energy_log) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != agent log {energy_log:.10f} Ha "
    f"(tol {cv_tol:.1e}) — log was not produced by this calculation",
)
check(
    abs(energy_re - energy_rep) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.10f} Ha != results.json {energy_rep:.10f} Ha "
    f"(tol {cv_tol:.1e})",
)

print("PASS: cp2k-h2o-sp")

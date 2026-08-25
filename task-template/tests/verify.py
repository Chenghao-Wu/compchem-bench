#!/usr/bin/env python3
"""
Verifier for <task-name>.

Four-layer terminal-state verification (see DATASET_CARD §3):
  1. File existence + results.json schema ({'values': ..., 'units': ...})
  2. Asset integrity: sha256 every consumed /workspace/assets file against
     refs.json["asset_hashes"] BEFORE any use (assets are agent-writable).
  3. Native-output integrity + self-reported sanity (the software's own log is
     present, complete, internally consistent).
  4. REAL RECOMPUTE (cross-verify / L4): rebuild the calculation from the
     agent's final state with the in-image software and require
     energy(agent log) == energy(results.json) == energy(recompute). Stub or
     hand-written files fail here.
  5. Reference tolerance vs refs.json (calibrated on the pinned image).

Any anomaly in the recompute layer is a hard fail — there is no warning
fallback. Never trust the workspace copy of any asset without re-hashing.
"""
import hashlib
import json
import os
import sys

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets")
REFS_PATH = "/tests/refs.json"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


# ── Load refs ─────────────────────────────────────────────────────────────────
with open(REFS_PATH) as f:
    refs = json.load(f)


# ── Layer 0: Asset integrity (do this before reading any asset) ───────────────
# Required whenever verify.py consumes anything under /workspace/assets.
# Delete the block if the task ships no assets (or leaves assets untrusted).
for rel, want in refs.get("asset_hashes", {}).items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"Missing asset required for verification: {rel}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    check(got == want, f"Asset {rel} sha256 mismatch (tampered?): {got} != {want}")


# ── Layer 1: File existence + schema ──────────────────────────────────────────
# TODO(author): enumerate every required output file.
for fname in ("results.json",):          # add the task's other outputs here
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing file: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

REQUIRED = ()  # TODO(author): e.g. ("final_energy", "max_force", ...)
for key in REQUIRED:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")


# ── Layer 2: Native-output integrity ──────────────────────────────────────────
# TODO(author): read the software's own log and confirm it is real and
# internally consistent, e.g. QE `pw.out` has "Program PWSCF v.X.Y", "JOB DONE.",
# and a converged "! total energy"; CP2K has "SCF run converged" and
# "GEOMETRY OPTIMIZATION COMPLETED"; LAMMPS has "Total wall time" and the
# thermo steps. A stub file must fail here.


# ── Layer 3: Self-reported sanity ─────────────────────────────────────────────
# TODO(author): check reported values against task-invariant thresholds
# (e.g. convergence criteria, stoichiometry, sign/range plausibility).


# ── Layer 4: REAL RECOMPUTE (cross-verify) ────────────────────────────────────
# TODO(author): rebuild the calculation from the agent's final state using the
# in-image software and require agreement with the reported values. This is the
# core anti-cheat layer — see tasks/ase-geoopt-h2o/tests/verify.py for the
# simplest (in-process ASE calculator) example, or
# tasks/qe-dihedral-scan-hexane/tests/verify.py for a subprocess pw.x recompute.
# e.g.:
#   recomputed = last_frame.copy()
#   recomputed.calc = <pinned calculator>
#   e_re = float(recomputed.get_potential_energy())
#   check(abs(e_re - values["final_energy"]) <= refs["crossverify_energy_tol_eV"], ...)


# ── Layer 5: Reference tolerance ──────────────────────────────────────────────
# TODO(author): compare the final (recomputed) value against refs.json:
#   check(abs(value - refs["<observable>_ref"]) <= refs["<observable>_tol"], ...)


print("PASS: <task-name>")

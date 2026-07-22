#!/usr/bin/env python3
"""
Verifier for xtb-singlepoint-gfn2:
  0. Asset integrity: sha256 of /workspace/assets/acetonitrile.xyz must
     match the pinned hash (the verifier never trusts the agent-writable
     copy)
  1. File existence + results.json schema (values/units)
  2. Output integrity (xtb banner, SCC convergence, normal termination)
  3. log <-> results consistency (TOTAL ENERGY / HOMO-LUMO GAP lines)
  4. Numerical tolerance vs calibrated refs (deterministic run)
  5. REAL RECOMPUTE (cross-verify): the verifier re-runs the same GFN2
     single point on the pinned asset geometry with the in-image xtb and
     requires three-way agreement:
         energy(agent log) == energy(results.json) == energy(recompute)
     Any recompute failure is a hard fail — no skip/warning path.
"""
import json
import sys
import os
import re
import hashlib
import shutil
import subprocess
import tempfile

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

ENERGY_RE = re.compile(r"TOTAL ENERGY\s+([-\d.]+)\s+Eh")
GAP_RE = re.compile(r"HOMO-LUMO GAP\s+([-\d.]+)\s+eV")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def parse_energy(content):
    m = ENERGY_RE.findall(content)
    if not m:
        fail("No 'TOTAL ENERGY' line found in xtb output")
    return float(m[-1])


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 0: Asset integrity ───────────────────────────────────────────────────
asset_rel = "assets/acetonitrile.xyz"
asset_path = os.path.join(WORKSPACE, asset_rel)
check(os.path.isfile(asset_path), f"Missing asset: {asset_rel}")
pinned = refs.get("asset_hashes", {}).get(asset_rel)
check(pinned, "refs.json asset_hashes missing pin for assets/acetonitrile.xyz")
digest = "sha256:" + hashlib.sha256(open(asset_path, "rb").read()).hexdigest()
check(digest == pinned,
      f"Asset {asset_rel} was modified (sha256 {digest} != pinned {pinned}) — "
      f"the verifier does not trust the agent-writable copy")

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("xtb_sp.out", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "homo_lumo_gap"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "xtb_sp.out")) as f:
    content = f.read()

check("x T B" in content or "xtb version" in content,
      "xtb_sp.out missing xtb banner")
check("normal termination of xtb" in content,
      "xtb_sp.out missing 'normal termination of xtb' — run did not finish cleanly")
check("convergence criteria satisfied" in content,
      "xtb_sp.out: SCC did not converge")
check("GEOMETRY OPTIMIZATION CONVERGED" not in content,
      "xtb_sp.out shows a geometry optimization — the task requires a single point")

# ── Layer 3: log <-> results consistency ───────────────────────────────────────
energy_log = parse_energy(content)
m = GAP_RE.findall(content)
check(m, "No 'HOMO-LUMO GAP' line found in xtb output")
gap_log = float(m[-1])

check(abs(energy_log - values["total_energy"]) <= refs["consistency_energy_tol_Eh"],
      f"results.json total_energy {values['total_energy']:.10f} != log "
      f"{energy_log:.10f} (tol {refs['consistency_energy_tol_Eh']:.1e})")
check(abs(gap_log - values["homo_lumo_gap"]) <= refs["consistency_gap_tol_eV"],
      f"results.json homo_lumo_gap {values['homo_lumo_gap']:.6f} != log "
      f"{gap_log:.6f} (tol {refs['consistency_gap_tol_eV']:.1e})")

# ── Layer 4: Reference tolerance (deterministic run) ───────────────────────────
check(abs(energy_log - refs["total_energy_Eh_ref"]) <= refs["total_energy_Eh_tol"],
      f"total_energy={energy_log:.10f} Eh differs from ref "
      f"{refs['total_energy_Eh_ref']:.10f} Eh by >{refs['total_energy_Eh_tol']:.1e}")
check(abs(gap_log - refs["homo_lumo_gap_eV_ref"]) <= refs["homo_lumo_gap_eV_tol"],
      f"homo_lumo_gap={gap_log:.6f} eV differs from ref "
      f"{refs['homo_lumo_gap_eV_ref']:.6f} eV by >{refs['homo_lumo_gap_eV_tol']:.1e}")

# ── Layer 5: REAL RECOMPUTE — same single point on the pinned geometry ────────
tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    shutil.copy(asset_path, os.path.join(tmpdir, "mol.xyz"))
    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["xtb", "mol.xyz", "--gfn", "2"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=300,
    )
    check(proc.returncode == 0,
          f"Cross-verify recompute: xtb exited with code {proc.returncode}\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    check("normal termination of xtb" in proc.stdout + proc.stderr,
          "Cross-verify recompute: xtb did not terminate normally")
    energy_re = parse_energy(proc.stdout)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Eh"]
check(
    abs(energy_re - energy_log) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.12f} Eh != agent log {energy_log:.12f} Eh "
    f"(tol {cv_tol:.1e})",
)
check(
    abs(energy_re - values["total_energy"]) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.12f} Eh != results.json "
    f"{values['total_energy']:.12f} Eh (tol {cv_tol:.1e})",
)

print("PASS: xtb-singlepoint-gfn2")

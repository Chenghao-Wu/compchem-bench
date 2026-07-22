#!/usr/bin/env python3
"""
Verifier for xtb-geoopt-caffeine:
  1. File existence + results.json schema (values/units)
  2. Output integrity (xtb banner, GEOMETRY OPTIMIZATION CONVERGED,
     normal termination)
  3. results.json sanity (opt_converged)
  4. log <-> results consistency (last TOTAL ENERGY, molecular dipole)
  5. Numerical tolerance vs calibrated refs (energy, dipole)
  6. Optimized-structure check (xtbopt.xyz exists, 24 atoms C8H10N4O2)
  7. REAL RECOMPUTE (cross-verify): the verifier runs a GFN2 single point
     on the agent's optimized geometry with the in-image xtb and requires
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
from collections import Counter

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

ENERGY_RE = re.compile(r"TOTAL ENERGY\s+([-\d.]+)\s+Eh")
DIPOLE_RE = re.compile(
    r"molecular dipole:.*?full:\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)",
    re.DOTALL,
)


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


def parse_xyz(path):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    natoms = int(lines[0])
    atoms = []
    for line in lines[2:2 + natoms]:
        p = line.split()
        atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))
    return atoms


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("xtb_opt.out", "xtbopt.xyz", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "dipole_moment", "opt_converged"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "xtb_opt.out")) as f:
    content = f.read()

check("x T B" in content or "xtb version" in content,
      "xtb_opt.out missing xtb banner")
check("GEOMETRY OPTIMIZATION CONVERGED" in content,
      "xtb_opt.out missing 'GEOMETRY OPTIMIZATION CONVERGED' — optimization "
      "did not converge")
check("normal termination of xtb" in content,
      "xtb_opt.out missing 'normal termination of xtb'")

# ── Layer 3: results.json sanity ───────────────────────────────────────────────
check(values["opt_converged"] is True, "opt_converged must be true")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
energy_log = parse_energy(content)
dip_match = DIPOLE_RE.search(content)
check(dip_match, "No 'molecular dipole' block found in xtb output")
dipole_log = float(dip_match.group(1))

check(abs(energy_log - values["final_energy"]) <= refs["consistency_energy_tol_Eh"],
      f"results.json final_energy {values['final_energy']:.10f} != log "
      f"{energy_log:.10f} (tol {refs['consistency_energy_tol_Eh']:.1e})")
check(abs(dipole_log - values["dipole_moment"]) <= refs["consistency_dipole_tol_D"],
      f"results.json dipole_moment {values['dipole_moment']:.4f} != log "
      f"{dipole_log:.4f} (tol {refs['consistency_dipole_tol_D']})")

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
check(abs(energy_log - refs["final_energy_Eh_ref"]) <= refs["final_energy_Eh_tol"],
      f"final_energy={energy_log:.10f} Eh differs from ref "
      f"{refs['final_energy_Eh_ref']:.10f} Eh by >{refs['final_energy_Eh_tol']:.1e}")
check(abs(dipole_log - refs["dipole_moment_D_ref"]) <= refs["dipole_moment_D_tol"],
      f"dipole_moment={dipole_log:.4f} Debye differs from ref "
      f"{refs['dipole_moment_D_ref']:.4f} Debye by >{refs['dipole_moment_D_tol']}")

# ── Layer 6: Optimized-structure check (required — hard fail if missing) ──────
atoms = parse_xyz(os.path.join(WORKSPACE, "xtbopt.xyz"))
check(len(atoms) == 24, f"xtbopt.xyz has {len(atoms)} atoms (expected 24: caffeine)")
counts = Counter(a[0] for a in atoms)
check(counts == Counter({"C": 8, "H": 10, "N": 4, "O": 2}),
      f"xtbopt.xyz composition {dict(counts)} != caffeine C8H10N4O2")

# ── Layer 7: REAL RECOMPUTE — single point on the agent's optimized geometry ──
xyz_lines = ["24", "crossverify single point"]
for sym, x, y, z in atoms:
    xyz_lines.append(f"{sym:2s}  {x:.10f}  {y:.10f}  {z:.10f}")

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "mol.xyz"), "w") as f:
        f.write("\n".join(xyz_lines) + "\n")
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
    f"(tol {cv_tol:.1e}) — log does not correspond to the optimized geometry",
)
check(
    abs(energy_re - values["final_energy"]) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.12f} Eh != results.json "
    f"{values['final_energy']:.12f} Eh (tol {cv_tol:.1e})",
)

print("PASS: xtb-geoopt-caffeine")

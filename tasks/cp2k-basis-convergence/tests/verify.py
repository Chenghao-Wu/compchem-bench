#!/usr/bin/env python3
"""
Verifier for cp2k-basis-convergence:
  0. Asset integrity: sha256 of /workspace/assets/methanol.xyz must match
     the pinned hash (the verifier never trusts the agent-writable copy)
  1. File existence + results.json schema (values/units)
  2. Output integrity per basis log (banner, SCF converged, normal
     termination, geometry in log matches the asset)
  3. log <-> results consistency (last ENERGY| line per basis)
  4. Physics: energies strictly decrease SZV -> DZVP -> TZVP; tolerance vs
     calibrated refs
  5. REAL RECOMPUTE (cross-verify): the verifier re-runs the cheapest
     (SZV) single point on the pinned asset geometry with the in-image
     CP2K and requires three-way agreement:
         energy(szv log) == energy(results.json) == energy(recompute)
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

ENERGY_RE = re.compile(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)")
BASES = ("szv", "dzvp", "tzvp")


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


def parse_log_geometry(content):
    """First ATOMIC COORDINATES block in a CP2K log -> [(elem, x, y, z)]."""
    idx = content.find("ATOMIC COORDINATES")
    check(idx >= 0, "No ATOMIC COORDINATES block in CP2K log")
    atoms = []
    pat = re.compile(r"^\s+\d+\s+\d+\s+([A-Za-z]+)\s+\d+\s+"
                     r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s")
    for line in content[idx:].splitlines()[1:]:
        m = pat.match(line)
        if m:
            atoms.append((m.group(1), float(m.group(2)),
                          float(m.group(3)), float(m.group(4))))
        elif atoms:
            break
    return atoms


def geometry_matches(asset_atoms, log_atoms, tol=1e-3):
    if len(asset_atoms) != len(log_atoms):
        return False
    used = [False] * len(log_atoms)
    for sym, x, y, z in asset_atoms:
        found = False
        for i, (lsym, lx, ly, lz) in enumerate(log_atoms):
            if used[i] or lsym != sym:
                continue
            if abs(lx - x) <= tol and abs(ly - y) <= tol and abs(lz - z) <= tol:
                used[i] = True
                found = True
                break
        if not found:
            return False
    return True


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 0: Asset integrity ───────────────────────────────────────────────────
asset_rel = "assets/methanol.xyz"
asset_path = os.path.join(WORKSPACE, asset_rel)
check(os.path.isfile(asset_path), f"Missing asset: {asset_rel}")
pinned = refs.get("asset_hashes", {}).get(asset_rel)
check(pinned, "refs.json asset_hashes missing pin for assets/methanol.xyz")
digest = "sha256:" + hashlib.sha256(open(asset_path, "rb").read()).hexdigest()
check(digest == pinned,
      f"Asset {asset_rel} was modified (sha256 {digest} != pinned {pinned}) — "
      f"the verifier does not trust the agent-writable copy")

asset_atoms = []
with open(asset_path) as f:
    xyz_lines = [l.strip() for l in f if l.strip()]
natoms = int(xyz_lines[0])
for line in xyz_lines[2:2 + natoms]:
    p = line.split()
    asset_atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for b in BASES:
    check(os.path.isfile(os.path.join(WORKSPACE, f"methanol_{b}.out")),
          f"Missing: methanol_{b}.out")
check(os.path.isfile(os.path.join(WORKSPACE, "results.json")), "Missing: results.json")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("energy_szv", "energy_dzvp", "energy_tzvp", "monotonic_decreasing"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity per basis log ────────────────────────────────────
log_energy = {}
for b in BASES:
    with open(os.path.join(WORKSPACE, f"methanol_{b}.out")) as f:
        content = f.read()
    check("CP2K" in content, f"methanol_{b}.out missing CP2K banner")
    check("SCF run converged" in content, f"methanol_{b}.out: SCF did not converge")
    check("PROGRAM ENDED AT" in content,
          f"methanol_{b}.out missing normal-termination footer")
    log_atoms = parse_log_geometry(content)
    check(geometry_matches(asset_atoms, log_atoms),
          f"methanol_{b}.out geometry does not match the pinned asset geometry")
    log_energy[b] = last_energy(content)

# ── Layer 3: log <-> results consistency ───────────────────────────────────────
cons_tol = refs["consistency_energy_tol_Ha"]
for b in BASES:
    rep = values[f"energy_{b}"]
    check(abs(log_energy[b] - rep) <= cons_tol,
          f"results.json energy_{b} {rep:.10f} != log {log_energy[b]:.10f} "
          f"(tol {cons_tol:.1e})")

# ── Layer 4: Physics + reference tolerance ─────────────────────────────────────
check(log_energy["szv"] > log_energy["dzvp"] > log_energy["tzvp"],
      f"Energies not monotonically decreasing with basis size: "
      f"SZV={log_energy['szv']:.8f} DZVP={log_energy['dzvp']:.8f} "
      f"TZVP={log_energy['tzvp']:.8f}")
check(values["monotonic_decreasing"] is True, "monotonic_decreasing must be true")

for b in BASES:
    ref = refs[f"energy_{b}_Ha_ref"]
    tol = refs[f"energy_{b}_Ha_tol"]
    check(abs(log_energy[b] - ref) <= tol,
          f"energy_{b}={log_energy[b]:.8f} Ha differs from ref {ref:.8f} Ha "
          f"by >{tol:.1e}")

# ── Layer 5: REAL RECOMPUTE — re-run the SZV point on the pinned geometry ─────
coord_lines = "\n".join(
    f"      {sym}   {x:.10f}   {y:.10f}   {z:.10f}"
    for sym, x, y, z in asset_atoms
)

sp_input = f"""&GLOBAL
  PROJECT crossverify_szv
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
    &KIND C
      BASIS_SET SZV-MOLOPT-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
    &KIND O
      BASIS_SET SZV-MOLOPT-GTH
      POTENTIAL GTH-PBE-q6
    &END KIND
    &KIND H
      BASIS_SET SZV-MOLOPT-GTH
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

    energy_re = last_energy(sp_content)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ha"]
check(
    abs(energy_re - log_energy["szv"]) <= cv_tol,
    f"Cross-verify: recomputed SZV {energy_re:.10f} Ha != agent SZV log "
    f"{log_energy['szv']:.10f} Ha (tol {cv_tol:.1e})",
)
check(
    abs(energy_re - values["energy_szv"]) <= cv_tol,
    f"Cross-verify: recomputed SZV {energy_re:.10f} Ha != results.json "
    f"{values['energy_szv']:.10f} Ha (tol {cv_tol:.1e})",
)

print("PASS: cp2k-basis-convergence")

#!/usr/bin/env python3
"""
Verifier for qe-dihedral-scan-hexane:
  1. File existence (7 scan dirs, pw.in/pw.out each, results.json) + schema
  2. Asset integrity: sha256 of the provided geometry and both
     pseudopotentials BEFORE any use — a tampered /workspace/assets copy
     is a hard fail
  3. Per-angle log integrity (PWSCF 7.4 banner, JOB DONE., converged `!`
     total energy) + pinned-setting echoes parsed from each pw.in
     (calculation, celldm(1), ecutwfc, ecutrho, occupations, conv_thr)
  4. Geometry truth: parse the 20-atom alat position table from each log;
     the C2-C3-C4-C5 dihedral must match the nominal angle, and all 19 bond
     lengths (5 C-C + 14 C-H, identified on the hash-verified asset) must
     match the provided geometry — a rigid scan cannot drift
  5. results.json <-> log consistency (total energies, relative energies via
     the pinned Ry->kcal/mol factor, derived keys)
  6. Numerical tolerance vs calibrated x86_64 reference per angle + derived
     quantities, plus physical sanity (ordering, min at 180 deg, plausible
     barrier windows)
  7. REAL RECOMPUTE (cross-verify / L4): for three angles the verifier
     rebuilds an SCF single point from the geometry parsed out of the
     agent's own log and runs it with the in-image pw.x, requiring
     three-way agreement:  energy(agent log) == energy(results.json)
     == energy(recompute).  Any recompute failure is a hard fail.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets")
REFS_PATH = "/tests/refs.json"
BOHR_TO_ANG = 0.529177210903
RY_TO_KCAL = 627.5094740631

GRID = [0, 30, 60, 90, 120, 150, 180]
# 0-based indices in the pinned atom order (C1..C6, then H grouped by carbon)
IC2, IC3, IC4, IC5 = 1, 2, 3, 4


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def vsub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def vnorm(a):
    n = math.sqrt(vdot(a, a))
    return [a[0] / n, a[1] / n, a[2] / n]


def dist(a, b):
    return math.sqrt(vdot(vsub(a, b), vsub(a, b)))


def dihedral(p0, p1, p2, p3):
    b0 = vsub(p0, p1)
    b1 = vsub(p2, p1)
    b2 = vsub(p3, p2)
    v = [b0[i] - vdot(b0, b1) / vdot(b1, b1) * b1[i] for i in range(3)]
    w = [b2[i] - vdot(b2, b1) / vdot(b1, b1) * b1[i] for i in range(3)]
    x = vdot(v, w)
    y = vdot(vcross(vnorm(b1), v), w)
    return math.degrees(math.atan2(y, x))


def read_xyz(path):
    lines = open(path).read().strip().splitlines()
    n = int(lines[0])
    atoms = []
    for line in lines[2:2 + n]:
        p = line.split()
        atoms.append((p[0], [float(p[1]), float(p[2]), float(p[3])]))
    return atoms


def parse_positions_alat(content):
    """First 'site n. atom positions (alat units)' table -> [(el, [x,y,z] A)]."""
    m_alat = re.search(r"lattice parameter \(alat\)\s*=\s*([\d.]+)\s*a\.u\.", content)
    if not m_alat:
        return None
    alat_bohr = float(m_alat.group(1))
    rows = re.findall(
        r"^\s*\d+\s+([A-Za-z]+)\s+tau\(\s*\d+\s*\)\s*=\s*"
        r"\(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\)\s*$",
        content, re.MULTILINE)
    if len(rows) < 20:
        return None
    atoms = []
    conv = alat_bohr * BOHR_TO_ANG
    for el, x, y, z in rows[:20]:
        atoms.append((el, [float(x) * conv, float(y) * conv, float(z) * conv]))
    return atoms


def parse_float(text):
    return float(text.replace("d", "e").replace("D", "E"))


def check_input_echoes(pw_in, phi):
    def setting(name):
        m = re.search(rf"{name}\s*=\s*('[^']*'|[-+0-9.deDE]+)", pw_in, re.IGNORECASE)
        return m.group(1) if m else None

    calc = setting("calculation")
    check(calc and calc.strip("'").lower() == "scf",
          f"phi={phi}: pw.in must have calculation = 'scf', got {calc}")
    occ = setting("occupations")
    check(occ and occ.strip("'").lower() == "fixed",
          f"phi={phi}: pw.in must have occupations = 'fixed', got {occ}")
    for name, want in (("ecutwfc", 50.0), ("ecutrho", 400.0),
                       ("conv_thr", 1.0e-9), (r"celldm\(1\)", 30.0)):
        got = setting(name)
        check(got is not None, f"phi={phi}: pw.in missing {name}")
        check(abs(parse_float(got) - want) < 1e-12,
              f"phi={phi}: pw.in {name} = {got}, expected {want}")


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ──────────────────────────────────────────
res_path = os.path.join(WORKSPACE, "results.json")
check(os.path.isfile(res_path), "Missing: results.json")

logs, inputs = {}, {}
for phi in GRID:
    rundir = os.path.join(WORKSPACE, "scan", f"phi_{phi:03d}")
    out_p = os.path.join(rundir, "pw.out")
    in_p = os.path.join(rundir, "pw.in")
    check(os.path.isfile(out_p), f"Missing: scan/phi_{phi:03d}/pw.out")
    check(os.path.isfile(in_p), f"Missing: scan/phi_{phi:03d}/pw.in")
    logs[phi] = open(out_p).read()
    inputs[phi] = open(in_p).read()

with open(res_path) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

REQUIRED_KEYS = ("dihedral_grid_deg", "total_energies_Ry",
                 "relative_energies_kcal_mol", "syn_barrier_kcal_mol",
                 "gauche_energy_kcal_mol", "eclipsed_barrier_kcal_mol")
for key in REQUIRED_KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

grid_rep = values["dihedral_grid_deg"]
check(isinstance(grid_rep, list) and len(grid_rep) == len(GRID)
      and all(abs(float(a) - b) < 1e-9 for a, b in zip(grid_rep, GRID)),
      f"dihedral_grid_deg must be {GRID}, got {grid_rep}")

energies_rep = values["total_energies_Ry"]
relative_rep = values["relative_energies_kcal_mol"]
check(isinstance(energies_rep, list) and len(energies_rep) == len(GRID),
      "total_energies_Ry must have one entry per grid angle")
check(isinstance(relative_rep, list) and len(relative_rep) == len(GRID),
      "relative_energies_kcal_mol must have one entry per grid angle")

# ── Layer 2: Asset integrity (before any use of assets) ──────────────────────
for rel, want in refs["asset_hashes"].items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"Missing asset required for verification: {rel}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    check(got == want, f"Asset {rel} sha256 mismatch (tampered?): {got} != {want}")

asset_atoms = read_xyz(os.path.join(ASSETS, "hexane_anti.xyz"))
check(len(asset_atoms) == 20, "asset hexane_anti.xyz must have 20 atoms")
bonds = []
for i in range(20):
    for j in range(i + 1, 20):
        ei, ej = asset_atoms[i][0], asset_atoms[j][0]
        d = dist(asset_atoms[i][1], asset_atoms[j][1])
        pair = "".join(sorted((ei, ej)))
        if pair == "CC" and d < 1.8:
            bonds.append((i, j, d))
        elif pair == "CH" and d < 1.3:
            bonds.append((i, j, d))
check(len(bonds) == 19, f"asset bond detection found {len(bonds)} bonds, expected 19")

# ── Layer 3: Per-angle log integrity + pinned-setting echoes ─────────────────
energies_log = {}
for phi in GRID:
    content = logs[phi]
    check(re.search(r"Program PWSCF v\.7\.4", content),
          f"phi={phi}: pw.out missing 'Program PWSCF v.7.4' version banner")
    check("JOB DONE." in content,
          f"phi={phi}: pw.out missing 'JOB DONE.' — run did not finish cleanly")
    m = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    check(m, f"phi={phi}: no converged '! total energy' in pw.out")
    energies_log[phi] = float(m[-1])
    check_input_echoes(inputs[phi], phi)

# ── Layer 4: Geometry truth (dihedral + rigid-scan bond fingerprint) ─────────
scan_atoms = {}
for phi in GRID:
    atoms = parse_positions_alat(logs[phi])
    check(atoms is not None and len(atoms) == 20,
          f"phi={phi}: could not parse the 20-atom alat position table from pw.out")
    check(sorted(a[0] for a in atoms) == sorted(a[0] for a in asset_atoms),
          f"phi={phi}: species in pw.out do not match C6H14")
    scan_atoms[phi] = atoms

    phi_obs = abs(dihedral(atoms[IC2][1], atoms[IC3][1],
                           atoms[IC4][1], atoms[IC5][1]))
    check(abs(phi_obs - phi) <= refs["dihedral_tol_deg"],
          f"phi={phi}: C2-C3-C4-C5 dihedral in the log is {phi_obs:.3f} deg, "
          f"expected {phi} (tol {refs['dihedral_tol_deg']})")

    for i, j, d_ref in bonds:
        d = dist(atoms[i][1], atoms[j][1])
        check(abs(d - d_ref) <= refs["bond_tol_A"],
              f"phi={phi}: bond {asset_atoms[i][0]}{i+1}-{asset_atoms[j][0]}{j+1} "
              f"= {d:.4f} A drifts from the provided geometry ({d_ref:.4f} A) by "
              f"more than {refs['bond_tol_A']} A — not a rigid rotation")

# ── Layer 5: results.json <-> log consistency ─────────────────────────────────
cons_tol = refs["consistency_energy_tol_Ry"]
for k, phi in enumerate(GRID):
    check(abs(energies_rep[k] - energies_log[phi]) <= cons_tol,
          f"phi={phi}: results.json energy {energies_rep[k]:.8f} Ry != log "
          f"{energies_log[phi]:.8f} Ry (tol {cons_tol:.1e})")

e_anti = energies_log[GRID[-1]]
rel_tol = refs["relative_energy_tol_kcal_mol"]
for k, phi in enumerate(GRID):
    want = (energies_log[phi] - e_anti) * RY_TO_KCAL
    check(abs(relative_rep[k] - want) <= rel_tol,
          f"phi={phi}: relative_energies_kcal_mol[{k}] = {relative_rep[k]:.6f} "
          f"!= (E-E_anti)*627.5094740631 = {want:.6f} (tol {rel_tol})")

for key, idx in (("syn_barrier_kcal_mol", 0), ("gauche_energy_kcal_mol", 2),
                 ("eclipsed_barrier_kcal_mol", 4)):
    check(abs(values[key] - relative_rep[idx]) <= rel_tol,
          f"{key} = {values[key]} disagrees with relative_energies_kcal_mol[{idx}] "
          f"= {relative_rep[idx]}")

# ── Layer 6: Reference tolerances + physical sanity ───────────────────────────
e_tol = refs["energy_Ry_tol"]
for k, phi in enumerate(GRID):
    ref = refs["energy_Ry_ref"][str(phi)]
    check(abs(energies_rep[k] - ref) <= e_tol,
          f"phi={phi}: energy {energies_rep[k]:.8f} Ry differs from ref "
          f"{ref:.8f} Ry by >{e_tol:.1e}")

for key in ("syn_barrier_kcal_mol", "gauche_energy_kcal_mol",
            "eclipsed_barrier_kcal_mol"):
    ref = refs[key + "_ref"]
    tol = refs[key + "_tol"]
    check(abs(values[key] - ref) <= tol,
          f"{key} = {values[key]:.4f} kcal/mol differs from ref {ref:.4f} by >{tol}")

check(relative_rep[GRID.index(180)] <= rel_tol,
      "anti (phi=180) point must be the zero of relative energies")
argmin = min(range(len(GRID)), key=lambda k: relative_rep[k])
check(argmin == GRID.index(180),
      f"profile minimum must be the anti 180 deg point, got index {argmin}")
for k, phi in enumerate(GRID[:-1]):
    check(relative_rep[k] > 0.1,
          f"phi={phi}: rigid-scan point {relative_rep[k]:.4f} kcal/mol must sit "
          f"at least 0.1 above the anti minimum")

# ── Layer 7: REAL RECOMPUTE — SCF single points on the agent's log geometries ─
cv_tol = refs["crossverify_energy_tol_Ry"]
for phi in refs["crossverify_angles_deg"]:
    atoms = scan_atoms[phi]
    positions = "\n".join(
        f"  {el} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}" for el, p in atoms
    )
    sp_input = f"""&CONTROL
  calculation = 'scf'
  prefix = 'crossverify'
  outdir = './cv_outdir'
  pseudo_dir = '{ASSETS}/pseudo'
/
&SYSTEM
  ibrav = 1
  celldm(1) = 30.0
  nat = 20
  ntyp = 2
  ecutwfc = 50.0
  ecutrho = 400.0
  occupations = 'fixed'
/
&ELECTRONS
  conv_thr = 1.0d-9
/
ATOMIC_SPECIES
  C 12.0107 C.pbe-n-kjpaw_psl.1.0.0.UPF
  H 1.00794 H.pbe-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS angstrom
{positions}
K_POINTS gamma
"""
    tmpdir = tempfile.mkdtemp(prefix=f"crossverify_{phi:03d}_")
    try:
        with open(os.path.join(tmpdir, "sp.in"), "w") as f:
            f.write(sp_input)
        proc = subprocess.run(
            ["pw.x", "-in", "sp.in"], cwd=tmpdir,
            capture_output=True, text=True, timeout=900,
        )
        sp_out = proc.stdout + proc.stderr
        check(proc.returncode == 0 and "JOB DONE." in sp_out,
              f"Cross-verify phi={phi}: pw.x failed (rc={proc.returncode})\n"
              f"{sp_out[-2000:]}")
        m_re = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", sp_out)
        check(m_re, f"Cross-verify phi={phi}: no total energy in pw.x output")
        energy_re = float(m_re[-1])
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    k = GRID.index(phi)
    check(abs(energy_re - energies_log[phi]) <= cv_tol,
          f"Cross-verify phi={phi}: recomputed {energy_re:.8f} Ry != agent log "
          f"{energies_log[phi]:.8f} Ry (tol {cv_tol:.1e}) — log does not "
          f"correspond to a real SCF run on this geometry")
    check(abs(energy_re - energies_rep[k]) <= cv_tol,
          f"Cross-verify phi={phi}: recomputed {energy_re:.8f} Ry != results.json "
          f"{energies_rep[k]:.8f} Ry (tol {cv_tol:.1e})")

print("PASS: qe-dihedral-scan-hexane")

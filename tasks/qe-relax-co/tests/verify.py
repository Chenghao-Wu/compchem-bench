#!/usr/bin/env python3
"""
Verifier for qe-relax-co:
  1. File existence + results.json schema (values/units)
  2. Asset integrity: sha256 of every asset the verifier consumes
     (pseudopotentials for the recompute) BEFORE any use — a tampered
     /workspace/assets copy is a hard fail
  3. Output integrity (PWSCF version banner, BFGS convergence marker,
     JOB DONE.)
  4. results.json sanity + log <-> results consistency (Final energy,
     final ATOMIC_POSITIONS bond length)
  5. Numerical tolerance vs calibrated x86_64 reference
  6. DOUBLE SOURCE: stdout final energy == XML <etot> (Ha -> Ry)
  7. REAL RECOMPUTE (cross-verify / L4): the verifier builds an SCF
     single-point input from the agent's final geometry (same cutoffs,
     box, smearing, pseudopotentials as the task input) and runs it with
     the in-image pw.x, requiring three-way agreement:
         energy(agent log) == energy(results.json) == energy(recompute)
     Any recompute failure is a hard fail — no skip/warning path.
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
import xml.etree.ElementTree as ET

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets")
REFS_PATH = "/tests/refs.json"
RY_PER_HA = 2.0


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ──────────────────────────────────────────
out_path = os.path.join(WORKSPACE, "co_relax.out")
xml_path = os.path.join(WORKSPACE, "outdir", "pwscf.xml")
res_path = os.path.join(WORKSPACE, "results.json")

check(os.path.isfile(out_path), "Missing: co_relax.out")
check(os.path.isfile(xml_path), "Missing: outdir/pwscf.xml (QE XML summary)")
check(os.path.isfile(res_path), "Missing: results.json")

with open(res_path) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "co_bond_length", "relax_converged", "n_bfgs_steps"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Asset integrity (before any use of assets) ──────────────────────
for rel, want in refs["asset_hashes"].items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"Missing asset required for verification: {rel}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    check(got == want, f"Asset {rel} sha256 mismatch (tampered?): {got} != {want}")

# ── Layer 3: Output integrity ─────────────────────────────────────────────────
with open(out_path) as f:
    content = f.read()

check(re.search(r"Program PWSCF v\.7\.4", content),
      "co_relax.out missing 'Program PWSCF v.7.4' version banner")
check("JOB DONE." in content, "co_relax.out missing 'JOB DONE.' — run did not finish cleanly")
m_bfgs = re.search(r"bfgs converged in\s+(\d+)\s+scf cycles and\s+(\d+)\s+bfgs steps", content)
check(m_bfgs, "Missing 'bfgs converged in ... scf cycles and ... bfgs steps' — BFGS did not converge")
check("End of BFGS Geometry Optimization" in content,
      "Missing 'End of BFGS Geometry Optimization'")

# ── Layer 4: results.json sanity + log <-> results consistency ───────────────
check(values["relax_converged"] is True, "relax_converged must be true")
check(isinstance(values["n_bfgs_steps"], int) and values["n_bfgs_steps"] >= 1,
      "n_bfgs_steps must be an integer >= 1")
check(values["n_bfgs_steps"] == int(m_bfgs.group(2)),
      f"n_bfgs_steps={values['n_bfgs_steps']} != log ({m_bfgs.group(2)})")

m_e = re.search(r"Final energy\s*=\s*([-\d.]+)\s+Ry", content)
check(m_e, "No 'Final energy' line found in co_relax.out")
energy_log = float(m_e.group(1))
energy_rep = values["final_energy"]
check(abs(energy_log - energy_rep) <= refs["consistency_energy_tol_Ry"],
      f"results.json energy {energy_rep:.8f} Ry != log Final energy {energy_log:.8f} Ry "
      f"(tol {refs['consistency_energy_tol_Ry']:.1e})")

# Final geometry: the ATOMIC_POSITIONS block between 'Begin final coordinates'
# and 'End final coordinates'
m_geo = re.search(
    r"Begin final coordinates\s+ATOMIC_POSITIONS \(angstrom\)\s+((?:\s*\w+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n)+)\s*End final coordinates",
    content)
check(m_geo, "Could not find the final ATOMIC_POSITIONS block in co_relax.out")
positions = []
for line in m_geo.group(1).strip().splitlines():
    parts = line.split()
    positions.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
check(len(positions) == 2 and sorted(p[0] for p in positions) == ["C", "O"],
      f"Final geometry must be a CO molecule, got {positions}")

c = next(p for p in positions if p[0] == "C")
o = next(p for p in positions if p[0] == "O")
bond_log = math.dist(c[1:], o[1:])
bond_rep = values["co_bond_length"]
check(abs(bond_log - bond_rep) <= refs["consistency_bond_tol_A"],
      f"results.json bond {bond_rep:.6f} Å != log bond {bond_log:.6f} Å "
      f"(tol {refs['consistency_bond_tol_A']})")

# ── Layer 5: Reference tolerance ──────────────────────────────────────────────
bond_ref, bond_tol = refs["co_bond_A_ref"], refs["co_bond_A_tol"]
check(abs(bond_rep - bond_ref) <= bond_tol,
      f"co_bond_length={bond_rep:.4f} Å differs from ref {bond_ref:.4f} Å by >{bond_tol}")
check(1.0 <= bond_rep <= 1.3, f"C-O bond {bond_rep:.4f} Å outside plausible range [1.0, 1.3]")

energy_ref, energy_tol = refs["final_energy_Ry_ref"], refs["final_energy_Ry_tol"]
check(abs(energy_rep - energy_ref) <= energy_tol,
      f"final_energy={energy_rep:.8f} Ry differs from ref {energy_ref:.8f} Ry by >{energy_tol:.2e}")

# ── Layer 6: Double source — stdout vs XML ────────────────────────────────────
try:
    root = ET.parse(xml_path).getroot()
except ET.ParseError as e:
    fail(f"outdir/pwscf.xml is not valid XML: {e}")
etot_el = root.find("./output/total_energy/etot")
check(etot_el is not None and etot_el.text, "pwscf.xml missing output/total_energy/etot")
energy_xml_ry = float(etot_el.text) * RY_PER_HA
check(abs(energy_xml_ry - energy_log) <= refs["xml_energy_tol_Ry"],
      f"XML etot {energy_xml_ry:.8f} Ry != stdout Final energy {energy_log:.8f} Ry "
      f"(tol {refs['xml_energy_tol_Ry']:.1e}) — the two QE sources disagree")

# ── Layer 7: REAL RECOMPUTE — SCF single point on the agent's final geometry ─
sp_input = f"""&CONTROL
  calculation = 'scf'
  prefix = 'crossverify'
  outdir = './cv_outdir'
  pseudo_dir = '{ASSETS}/pseudo'
/
&SYSTEM
  ibrav = 1
  celldm(1) = 20.0
  nat = 2
  ntyp = 2
  ecutwfc = 50.0
  ecutrho = 400.0
  occupations = 'smearing'
  smearing = 'mv'
  degauss = 0.01
/
&ELECTRONS
  conv_thr = 1.0d-9
/
ATOMIC_SPECIES
  C 12.0107 C.pbe-n-kjpaw_psl.1.0.0.UPF
  O 15.9994 O.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS angstrom
  C {c[1]:.10f} {c[2]:.10f} {c[3]:.10f}
  O {o[1]:.10f} {o[2]:.10f} {o[3]:.10f}
K_POINTS gamma
"""

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "sp.in"), "w") as f:
        f.write(sp_input)
    proc = subprocess.run(
        ["pw.x", "-in", "sp.in"], cwd=tmpdir,
        capture_output=True, text=True, timeout=600,
    )
    sp_out = proc.stdout + proc.stderr
    check(proc.returncode == 0 and "JOB DONE." in sp_out,
          f"Cross-verify recompute: pw.x failed (rc={proc.returncode})\n{sp_out[-2000:]}")
    m_re = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", sp_out)
    check(m_re, "Cross-verify recompute: no total energy in pw.x output")
    energy_re = float(m_re[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ry"]
check(abs(energy_re - energy_log) <= cv_tol,
      f"Cross-verify: recomputed {energy_re:.8f} Ry != agent log {energy_log:.8f} Ry "
      f"(tol {cv_tol:.1e}) — log does not correspond to the claimed final geometry")
check(abs(energy_re - energy_rep) <= cv_tol,
      f"Cross-verify: recomputed {energy_re:.8f} Ry != results.json {energy_rep:.8f} Ry "
      f"(tol {cv_tol:.1e})")

print("PASS: qe-relax-co")

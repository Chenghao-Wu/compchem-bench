#!/usr/bin/env python3
"""
Verifier for qe-scf-si:
  1. File existence + results.json schema (values/units)
  2. Output integrity (PWSCF version banner, SCF iteration table,
     convergence line, JOB DONE.)
  3. Calculation settings echoed in the log match the task input
     (ecutwfc = 40 Ry, 10 irreducible k-points, 2 atoms) — the agent must
     not have weakened the provided input
  4. results.json sanity + log <-> results consistency
  5. DOUBLE SOURCE: stdout '! total energy' == XML <etot> (converted Ha->Ry)
  6. Numerical tolerance vs calibrated x86_64 reference
"""
import json
import re
import sys
import os
import xml.etree.ElementTree as ET

WORKSPACE = "/workspace"
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
out_path = os.path.join(WORKSPACE, "si_scf.out")
xml_path = os.path.join(WORKSPACE, "outdir", "pwscf.xml")
res_path = os.path.join(WORKSPACE, "results.json")

check(os.path.isfile(out_path), "Missing: si_scf.out")
check(os.path.isfile(xml_path), "Missing: outdir/pwscf.xml (QE XML summary)")
check(os.path.isfile(res_path), "Missing: results.json")

with open(res_path) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "scf_converged", "n_scf_iterations"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ─────────────────────────────────────────────────
with open(out_path) as f:
    content = f.read()

check(re.search(r"Program PWSCF v\.7\.4", content),
      "si_scf.out missing 'Program PWSCF v.7.4' version banner")
check("JOB DONE." in content, "si_scf.out missing 'JOB DONE.' — run did not finish cleanly")

iterations = re.findall(r"iteration #\s*\d+", content)
check(len(iterations) >= 3,
      f"SCF iteration table too short ({len(iterations)} iteration lines) — not a real pw.x log")
check("convergence has been achieved" in content,
      "Missing 'convergence has been achieved' — SCF did not converge")

# ── Layer 3: Settings echoed in the log must match the task input ─────────────
check(re.search(r"kinetic-energy cutoff\s*=\s*40\.0000\s+Ry", content),
      "ecutwfc is not 40.00 Ry in the log — the provided input must be run unmodified")
m = re.search(r"number of k points=\s*(\d+)", content)
check(m and int(m.group(1)) == 10,
      f"Expected 10 irreducible k-points (4x4x4 shifted grid), found {m.group(1) if m else 'none'}")
m = re.search(r"number of atoms/cell\s*=\s*([\d.]+)", content)
check(m and abs(float(m.group(1)) - 2.0) < 1e-6,
      f"Expected 2 atoms/cell, found {m.group(1) if m else 'none'}")

# ── Layer 4: results.json sanity + log <-> results consistency ───────────────
check(values["scf_converged"] is True, "scf_converged must be true")
check(isinstance(values["n_scf_iterations"], int) and values["n_scf_iterations"] >= 1,
      "n_scf_iterations must be an integer >= 1")
check(values["n_scf_iterations"] == len(iterations),
      f"n_scf_iterations={values['n_scf_iterations']} != iteration lines in log ({len(iterations)})")

energy_matches = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
check(energy_matches, "No '! total energy' line found in si_scf.out")
energy_log = float(energy_matches[-1])
energy_rep = values["total_energy"]

check(abs(energy_log - energy_rep) <= refs["consistency_energy_tol_Ry"],
      f"results.json energy {energy_rep:.8f} Ry != log energy {energy_log:.8f} Ry "
      f"(tol {refs['consistency_energy_tol_Ry']:.1e})")

# ── Layer 5: Double source — stdout vs XML ────────────────────────────────────
try:
    root = ET.parse(xml_path).getroot()
except ET.ParseError as e:
    fail(f"outdir/pwscf.xml is not valid XML: {e}")
etot_el = root.find("./output/total_energy/etot")
check(etot_el is not None and etot_el.text, "pwscf.xml missing output/total_energy/etot")
energy_xml_ry = float(etot_el.text) * RY_PER_HA  # XML stores energies in Hartree

check(abs(energy_xml_ry - energy_log) <= refs["xml_energy_tol_Ry"],
      f"XML etot {energy_xml_ry:.8f} Ry != stdout energy {energy_log:.8f} Ry "
      f"(tol {refs['xml_energy_tol_Ry']:.1e}) — the two QE sources disagree")

# ── Layer 6: Reference tolerance ──────────────────────────────────────────────
energy_ref = refs["total_energy_Ry_ref"]
energy_tol = refs["total_energy_Ry_tol"]
check(abs(energy_rep - energy_ref) <= energy_tol,
      f"total_energy={energy_rep:.8f} Ry differs from ref {energy_ref:.8f} Ry by >{energy_tol:.2e}")

print("PASS: qe-scf-si")

#!/usr/bin/env python3
"""
Verifier for qe-output-parse:
  1. File existence + results.json schema (values/units)
  2. Asset integrity: sha256 of si_sample.out and pwscf.xml BEFORE any
     parsing — a tampered /workspace/assets copy is a hard fail
  3. Artifact coherence: the XML <etot>/<fermi_energy> must agree with the
     text output (Ha -> Ry / eV conversion) — both files describe one run
  4. REAL RE-PARSE (analysis cross-verify): the verifier independently
     parses the (hash-verified) artifacts and requires the agent's
     results.json to match within tight tolerances — the strongest layer
     for a deterministic analysis task
"""
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets", "sample_run")
REFS_PATH = "/tests/refs.json"
RY_PER_HA = 2.0
EV_PER_HA = 27.211386245988  # CODATA 2018


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def parse_stdout(content):
    """Extract (final_energy Ry, total_force Ry/bohr, fermi_energy eV)."""
    m_e = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    check(m_e, "sample_run/si_sample.out has no '! total energy' line")
    m_f = re.search(r"the Fermi energy is\s+([-\d.]+)\s+ev", content)
    check(m_f, "sample_run/si_sample.out has no Fermi energy line")
    m_t = re.search(r"Total force =\s+([-\d.]+)", content)
    check(m_t, "sample_run/si_sample.out has no 'Total force' line")
    return float(m_e[-1]), float(m_t.group(1)), float(m_f.group(1))


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ──────────────────────────────────────────
out_path = os.path.join(ASSETS, "si_sample.out")
xml_path = os.path.join(ASSETS, "pwscf.xml")
res_path = os.path.join(WORKSPACE, "results.json")

check(os.path.isfile(out_path), "Missing: assets/sample_run/si_sample.out")
check(os.path.isfile(xml_path), "Missing: assets/sample_run/pwscf.xml")
check(os.path.isfile(res_path), "Missing: results.json")

with open(res_path) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("final_energy", "total_force", "fermi_energy"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
    check(isinstance(values[key], (int, float)) and not isinstance(values[key], bool),
          f"results.json values[{key!r}] must be a number")

# ── Layer 2: Asset integrity (before any parsing) ────────────────────────────
for rel, want in refs["asset_hashes"].items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"Missing asset required for verification: {rel}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    check(got == want, f"Asset {rel} sha256 mismatch (tampered?): {got} != {want}")

# ── Layer 3: Artifact coherence (stdout vs XML of the same run) ───────────────
with open(out_path) as f:
    content = f.read()
check(re.search(r"Program PWSCF v\.7\.4", content),
      "si_sample.out missing 'Program PWSCF v.7.4' banner")
check("JOB DONE." in content, "si_sample.out missing 'JOB DONE.'")

energy_txt, force_txt, fermi_txt = parse_stdout(content)

try:
    root = ET.parse(xml_path).getroot()
except ET.ParseError as e:
    fail(f"sample_run/pwscf.xml is not valid XML: {e}")
etot_el = root.find("./output/total_energy/etot")
check(etot_el is not None and etot_el.text, "pwscf.xml missing output/total_energy/etot")
energy_xml_ry = float(etot_el.text) * RY_PER_HA
check(abs(energy_xml_ry - energy_txt) <= 1e-6,
      f"Artifact incoherent: XML etot {energy_xml_ry:.8f} Ry != stdout {energy_txt:.8f} Ry")
fermi_el = root.find("./output/band_structure/fermi_energy")
check(fermi_el is not None and fermi_el.text, "pwscf.xml missing band_structure/fermi_energy")
fermi_xml_ev = float(fermi_el.text) * EV_PER_HA
check(abs(fermi_xml_ev - fermi_txt) <= 5e-2,
      f"Artifact incoherent: XML fermi {fermi_xml_ev:.4f} eV != stdout {fermi_txt:.4f} eV")

# ── Layer 4: Real re-parse vs refs, then agent results vs refs ───────────────
# refs were calibrated from these very artifacts; the verifier's own parse
# must reproduce them (guards against parser drift).
check(abs(energy_txt - refs["final_energy_Ry_ref"]) <= 1e-8,
      f"Verifier re-parse {energy_txt:.8f} Ry != ref {refs['final_energy_Ry_ref']:.8f} Ry")
check(abs(force_txt - refs["total_force_RyB_ref"]) <= 1e-8,
      f"Verifier re-parse {force_txt:.6f} Ry/bohr != ref {refs['total_force_RyB_ref']:.6f}")
check(abs(fermi_txt - refs["fermi_energy_eV_ref"]) <= 1e-8,
      f"Verifier re-parse {fermi_txt:.4f} eV != ref {refs['fermi_energy_eV_ref']:.4f} eV")

e_rep, f_rep, ef_rep = values["final_energy"], values["total_force"], values["fermi_energy"]
check(abs(e_rep - refs["final_energy_Ry_ref"]) <= refs["final_energy_Ry_tol"],
      f"final_energy={e_rep} Ry differs from ref by >{refs['final_energy_Ry_tol']:.1e}")
check(abs(f_rep - refs["total_force_RyB_ref"]) <= refs["total_force_RyB_tol"],
      f"total_force={f_rep} Ry/bohr differs from ref by >{refs['total_force_RyB_tol']:.1e}")
check(abs(ef_rep - refs["fermi_energy_eV_ref"]) <= refs["fermi_energy_eV_tol"],
      f"fermi_energy={ef_rep} eV differs from ref by >{refs['fermi_energy_eV_tol']:.1e}")

print("PASS: qe-output-parse")

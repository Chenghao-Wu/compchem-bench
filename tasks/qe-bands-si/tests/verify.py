#!/usr/bin/env python3
"""
Verifier for qe-bands-si:
  1. File existence (three inputs, three logs, bands.dat, outdir/pwscf.xml,
     results.json schema)
  2. Workflow cross-references: si_scf.in calculation='scf', si_bands.in
     calculation='bands' with nbnd=8, both with the SAME prefix and outdir;
     bandsx.in &BANDS with the same prefix/outdir — the three steps really
     chain through the same charge density
  3. Log integrity: scf (banner, JOB DONE., convergence, ecut 40 Ry echo,
     10 irreducible k-points), bands (banner, JOB DONE., 21 k-points, 8 KS
     states), bands.x (BANDS banner, JOB DONE.)
  4. bands.dat structure: &plot nbnd=8, nks=21 header + 21 k/eigenvalue rows
  5. L4 — independent re-derivation from the raw XML eigenvalues:
     outdir/pwscf.xml band_structure (nbnd=8, nks=21, nelec=8) -> band 4/5
     eigenvalues at Gamma and X, VBM, CBM, indirect gap; results.json must
     match the XML-derived values
  6. bands.dat double source: the same quantities parsed from bands.dat must
     match results.json
  7. Numerical tolerance vs calibrated x86_64 references
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"
HA_TO_EV = 27.211386245988
KEYS = ("gamma_band4_eV", "gamma_band5_eV", "x_band4_eV", "x_band5_eV",
        "vbm_eV", "cbm_eV", "indirect_gap_eV")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)


def parse_namelists(text):
    """Minimal namelist parser: returns {name: {key: value-as-string}}."""
    nls = {}
    for m in re.finditer(r"&(\w+)\b(.*?)/", text, re.DOTALL):
        name, body = m.group(1).lower(), m.group(2)
        entries = {}
        for em in re.finditer(r"(\w+(?:\(\d+\))?)\s*=\s*('[^']*'|\"[^\"]*\"|[^,\n]+)", body):
            k, v = em.group(1).lower(), em.group(2).strip()
            entries[k] = v.strip("'\"")
        nls[name] = entries
    return nls


# ── Layer 1: File existence + schema ──────────────────────────────────────────
paths = {n: os.path.join(WORKSPACE, n) for n in
         ("si_scf.in", "si_scf.out", "si_bands.in", "si_bands.out",
          "bandsx.in", "bandsx.out", "bands.dat", "results.json")}
paths["xml"] = os.path.join(WORKSPACE, "outdir", "pwscf.xml")
for name, p in paths.items():
    check(os.path.isfile(p), f"Missing: {name if name != 'xml' else 'outdir/pwscf.xml'}")

with open(paths["results.json"]) as f:
    results = json.load(f)
check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]
for key in KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
rep = {k: float(values[k]) for k in KEYS}

# ── Layer 2: Workflow cross-references ────────────────────────────────────────
scf_in = parse_namelists(open(paths["si_scf.in"]).read())
bands_in = parse_namelists(open(paths["si_bands.in"]).read())
bandsx_in = parse_namelists(open(paths["bandsx.in"]).read())

check("control" in scf_in and "control" in bands_in,
      "si_scf.in / si_bands.in must contain &CONTROL namelists")
check(scf_in["control"].get("calculation", "").lower() == "scf",
      "si_scf.in must have calculation='scf'")
check(bands_in["control"].get("calculation", "").lower() == "bands",
      "si_bands.in must have calculation='bands'")
check("bands" in bandsx_in, "bandsx.in must contain a &BANDS namelist")

pfx_s, out_s = scf_in["control"].get("prefix"), scf_in["control"].get("outdir")
pfx_b, out_b = bands_in["control"].get("prefix"), bands_in["control"].get("outdir")
check(pfx_s and pfx_s == pfx_b,
      f"prefix mismatch: scf {pfx_s!r} vs bands {pfx_b!r} — the bands step must reuse the scf data")
check(out_s and out_s == out_b,
      f"outdir mismatch: scf {out_s!r} vs bands {out_b!r} — the bands step must reuse the scf data")
check(bandsx_in["bands"].get("prefix") == pfx_s,
      "bandsx.in prefix does not match the scf/bands prefix")
check(bandsx_in["bands"].get("outdir") == out_s,
      "bandsx.in outdir does not match the scf/bands outdir")

nbnd = bands_in.get("system", {}).get("nbnd")
check(nbnd is not None and int(float(nbnd)) == 8,
      f"si_bands.in must set nbnd=8, got {nbnd!r}")

# ── Layer 3: Log integrity ────────────────────────────────────────────────────
scf_out = open(paths["si_scf.out"]).read()
check(re.search(r"Program PWSCF v\.7\.4", scf_out),
      "si_scf.out missing 'Program PWSCF v.7.4' banner")
check("JOB DONE." in scf_out, "si_scf.out missing 'JOB DONE.'")
check("convergence has been achieved" in scf_out,
      "si_scf.out: SCF did not converge")
check(re.search(r"kinetic-energy cutoff\s*=\s*40\.0000\s+Ry", scf_out),
      "si_scf.out: ecutwfc echo is not 40.0000 Ry")
m = re.search(r"number of k points=\s*(\d+)", scf_out)
check(m and int(m.group(1)) == 10,
      f"si_scf.out: expected 10 irreducible k-points, found {m.group(1) if m else 'none'}")

bands_out = open(paths["si_bands.out"]).read()
check(re.search(r"Program PWSCF v\.7\.4", bands_out),
      "si_bands.out missing 'Program PWSCF v.7.4' banner")
check("JOB DONE." in bands_out, "si_bands.out missing 'JOB DONE.'")
check(re.search(r"number of Kohn-Sham states=\s*8\b", bands_out),
      "si_bands.out: expected 8 Kohn-Sham states (nbnd=8)")
check(re.search(r"kinetic-energy cutoff\s*=\s*40\.0000\s+Ry", bands_out),
      "si_bands.out: ecutwfc echo is not 40.0000 Ry")
m = re.search(r"number of k points=\s*(\d+)", bands_out)
check(m and int(m.group(1)) == 21,
      f"si_bands.out: expected 21 k-points on the path, found {m.group(1) if m else 'none'}")

bandsx_out = open(paths["bandsx.out"]).read()
check(re.search(r"Program BANDS v\.7\.4", bandsx_out),
      "bandsx.out missing 'Program BANDS v.7.4' banner")
check("JOB DONE." in bandsx_out, "bandsx.out missing 'JOB DONE.'")

# ── Layer 4: bands.dat structure ─────────────────────────────────────────────
dat_lines = [l for l in open(paths["bands.dat"]).read().splitlines() if l.strip()]
check(re.search(r"&plot\s+nbnd=\s*8,\s*nks=\s*21\s*/", dat_lines[0]),
      f"bands.dat header must be '&plot nbnd= 8, nks= 21 /', got {dat_lines[0]!r}")
check(len(dat_lines) >= 1 + 2 * 21,
      f"bands.dat must contain 21 k-point rows (each k line + eigenvalue line), "
      f"got {len(dat_lines) - 1} rows")

dat_k, dat_e = [], []
i = 1
while i < len(dat_lines) and len(dat_k) < 21:
    kvals = [float(x) for x in dat_lines[i].split()]
    evals = [float(x) for x in dat_lines[i + 1].split()]
    dat_k.append(kvals)
    dat_e.append(evals)
    i += 2
check(len(dat_k) == 21, "bands.dat: could not parse 21 k-point/eigenvalue rows")
check(all(len(e) == 8 for e in dat_e), "bands.dat: each k-point must have 8 eigenvalues")

# ── Layer 5: L4 — re-derive everything from the raw XML eigenvalues ──────────
try:
    root = ET.parse(paths["xml"]).getroot()
except ET.ParseError as e:
    fail(f"outdir/pwscf.xml is not valid XML: {e}")
bs = root.find("./output/band_structure")
check(bs is not None, "pwscf.xml missing output/band_structure")
check(int(bs.find("nbnd").text) == 8, f"XML nbnd must be 8, got {bs.find('nbnd').text}")
check(int(bs.find("nks").text) == 21, f"XML nks must be 21, got {bs.find('nks').text}")
nelec = float(bs.find("nelec").text)
check(abs(nelec - 8.0) < 1e-6, f"XML nelec must be 8 (4 filled bands), got {nelec}")

ks = bs.findall("ks_energies")
check(len(ks) == 21, f"XML must list 21 ks_energies blocks, got {len(ks)}")
xml_k, xml_e = [], []
for k in ks:
    xml_k.append([float(x) for x in k.find("k_point").text.split()])
    xml_e.append([float(x) * HA_TO_EV for x in k.find("eigenvalues").text.split()])
check(all(len(e) == 8 for e in xml_e), "XML: each k-point must have 8 eigenvalues")

i_gamma = [i for i, k in enumerate(xml_k) if all(abs(c) < 1e-8 for c in k)]
i_x = [i for i, k in enumerate(xml_k)
       if abs(k[0] - 1.0) < 1e-6 and abs(k[1]) < 1e-6 and abs(k[2]) < 1e-6]
check(len(i_gamma) == 1, f"XML: expected exactly one Gamma k-point, got {len(i_gamma)}")
check(len(i_x) == 1, f"XML: expected exactly one X=(1,0,0) k-point, got {len(i_x)}")
i_gamma, i_x = i_gamma[0], i_x[0]

b4 = [e[3] for e in xml_e]
b5 = [e[4] for e in xml_e]
derived = {
    "gamma_band4_eV": b4[i_gamma],
    "gamma_band5_eV": b5[i_gamma],
    "x_band4_eV": b4[i_x],
    "x_band5_eV": b5[i_x],
    "vbm_eV": max(b4),
    "cbm_eV": min(b5),
}
derived["indirect_gap_eV"] = derived["cbm_eV"] - derived["vbm_eV"]

xml_tol = refs["xml_consistency_tol_eV"]
for key in KEYS:
    check(abs(rep[key] - derived[key]) <= xml_tol,
          f"results.json {key}={rep[key]:.6f} eV != XML-derived {derived[key]:.6f} eV "
          f"(tol {xml_tol}) — report not backed by the raw XML eigenvalues")

# ── Layer 6: bands.dat double source ─────────────────────────────────────────
dat_b4 = [e[3] for e in dat_e]
dat_b5 = [e[4] for e in dat_e]
dat_g = next(i for i, k in enumerate(dat_k) if all(abs(c) < 1e-8 for c in k))
dat_x = next(i for i, k in enumerate(dat_k)
             if abs(k[0] - 1.0) < 1e-6 and abs(k[1]) < 1e-6 and abs(k[2]) < 1e-6)
dat_derived = {
    "gamma_band4_eV": dat_b4[dat_g],
    "gamma_band5_eV": dat_b5[dat_g],
    "x_band4_eV": dat_b4[dat_x],
    "x_band5_eV": dat_b5[dat_x],
    "vbm_eV": max(dat_b4),
    "cbm_eV": min(dat_b5),
}
dat_derived["indirect_gap_eV"] = dat_derived["cbm_eV"] - dat_derived["vbm_eV"]
dat_tol = refs["bandsdat_consistency_tol_eV"]
for key in KEYS:
    check(abs(rep[key] - dat_derived[key]) <= dat_tol,
          f"results.json {key}={rep[key]:.6f} eV != bands.dat-derived "
          f"{dat_derived[key]:.6f} eV (tol {dat_tol})")

# ── Layer 7: Reference tolerance ──────────────────────────────────────────────
for key in KEYS:
    ref, tol = refs["refs_eV"][key], refs["ref_tol_eV"][key]
    check(abs(rep[key] - ref) <= tol,
          f"{key}={rep[key]:.6f} eV differs from ref {ref:.6f} eV by >{tol}")

print("PASS: qe-bands-si")

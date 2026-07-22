#!/usr/bin/env python3
"""
Verifier for ase-format-convert:
  0. ASSET INTEGRITY: the CIF is the conversion ground truth and lives in
     agent-writable /workspace/assets — validate its pinned sha256 first.
  1. File existence + results.json schema (values/units)
  2. extxyz fidelity: cell / species / positions match the CIF (1e-4)
  3. LAMMPS data fidelity: same structural comparison via ASE, plus
     Masses-section element<->type mapping consistent with results.json
  4. L4-lite REAL READ: the LAMMPS engine itself does read_data + run 0 on
     nacl.data — a file LAMMPS cannot parse is a hard fail regardless of
     what ASE thinks of it. Box dimensions must match the CIF cell.
  5. Reference anchors (atom count, lattice parameter).
"""
import hashlib
import json
import sys
import os

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 0: ASSET INTEGRITY — never trust the workspace copy ────────────────
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
for fname in ("nacl.extxyz", "nacl.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_atoms", "n_types", "type_na", "type_cl"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Reference structure from the (hash-validated) CIF ────────────────────────
from ase.io import read

ref = read(os.path.join(WORKSPACE, "assets", "nacl.cif"))
ref_cell = np.array(ref.cell)
ref_len = float(np.linalg.norm(ref_cell[0]))

POS_TOL = refs["position_tol_frac"]
CELL_TOL = refs["cell_tol_A"]


def frac_by_element(atoms):
    """{element: sorted fractional positions (mod 1)}."""
    atoms = atoms.copy()
    atoms.pbc = True
    out = {}
    fracs = atoms.get_scaled_positions() % 1.0
    for el in set(atoms.get_chemical_symbols()):
        idx = [i for i, s in enumerate(atoms.get_chemical_symbols()) if s == el]
        pts = fracs[idx]
        pts = pts[np.lexsort((pts[:, 2], pts[:, 1], pts[:, 0]))]
        out[el] = pts
    return out


def compare_structure(atoms, label):
    check(len(atoms) == len(ref),
          f"{label}: {len(atoms)} atoms (expected {len(ref)})")
    check(sorted(atoms.get_chemical_symbols()) == sorted(ref.get_chemical_symbols()),
          f"{label}: species {sorted(set(atoms.get_chemical_symbols()))} != CIF species")
    cell = np.array(atoms.cell)
    check(abs(cell - ref_cell).max() <= CELL_TOL,
          f"{label}: cell {cell.tolist()} != CIF cell (tol {CELL_TOL} Å)")
    got = frac_by_element(atoms)
    want = frac_by_element(ref)
    for el, w in want.items():
        g = got[el]
        d = abs(g - w) % 1.0
        d = np.minimum(d, 1.0 - d)
        check(d.max() <= POS_TOL,
              f"{label}: {el} positions deviate from CIF by up to "
              f"{d.max():.2e} in fractional coords (tol {POS_TOL})")


# ── Layer 2: extxyz fidelity ──────────────────────────────────────────────────
extxyz = read(os.path.join(WORKSPACE, "nacl.extxyz"))
compare_structure(extxyz, "nacl.extxyz")

# ── Layer 3: LAMMPS data fidelity — element<->type mapping from STRUCTURE ────
# ASE's writer does not emit a Masses section, so the mapping is derived
# structurally: group data-file positions by atom type, convert to fractional
# coordinates, and match each type's position set against the CIF's Na/Cl
# position sets. A type whose positions coincide with the CIF Na sites IS Na;
# swapped or scrambled types fail the position comparison.
with open(os.path.join(WORKSPACE, "nacl.data")) as f:
    data_text = f.read()

import re

box_m = re.findall(r"^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+[xyz]lo [xyz]hi\s*$",
                   data_text, re.MULTILINE)
check(len(box_m) == 3, "nacl.data: expected 3 'xlo xhi'-style box lines")
box_lo = np.array([float(b[0]) for b in box_m])
box_hi = np.array([float(b[1]) for b in box_m])
box_len = box_hi - box_lo
check(abs(box_len - ref_len).max() <= CELL_TOL,
      f"nacl.data box lengths {box_len} != CIF cell {ref_len} (tol {CELL_TOL})")

atoms_m = re.search(r"Atoms[^\n]*\n\s*\n((?:\s*\d+\s+\d+\s+[-\d.eE+]+\s+[-\d.eE+]+\s+[-\d.eE+]+\s*\n?)+)",
                    data_text)
check(atoms_m is not None, "nacl.data: no parseable 'Atoms # atomic' section")
type_pos = {}
for line in atoms_m.group(1).strip().splitlines():
    p = line.split()
    if len(p) >= 5:
        t = int(p[1])
        type_pos.setdefault(t, []).append([float(p[2]), float(p[3]), float(p[4])])
check(type_pos, "nacl.data: Atoms section is empty")

n_total = sum(len(v) for v in type_pos.values())
check(n_total == len(ref), f"nacl.data has {n_total} atoms (expected {len(ref)})")
check(len(type_pos) == values["n_types"],
      f"nacl.data uses {len(type_pos)} atom types, results.json claims {values['n_types']}")

ref_fracs = frac_by_element(ref)


def frac_set_match(cart_list, want_frac):
    got = (np.array(cart_list) - box_lo) / box_len % 1.0
    if len(got) != len(want_frac):
        return False
    got = got[np.lexsort((got[:, 2], got[:, 1], got[:, 0]))]
    d = abs(got - want_frac) % 1.0
    d = np.minimum(d, 1.0 - d)
    return d.max() <= POS_TOL


type_of_el = {}
for t, plist in type_pos.items():
    matched = [el for el in ("Na", "Cl") if frac_set_match(plist, ref_fracs[el])]
    check(len(matched) == 1,
          f"nacl.data type {t}: positions match {matched or 'neither'} CIF "
          f"element set — the data file does not reproduce the CIF structure")
    type_of_el[matched[0]] = t
check("Na" in type_of_el and "Cl" in type_of_el,
      f"nacl.data types do not cover both Na and Cl sites: {type_of_el}")
check(type_of_el["Na"] != type_of_el["Cl"], "Na and Cl must have distinct types")
check(values["type_na"] == type_of_el["Na"],
      f"results.json type_na={values['type_na']} != data file Na type {type_of_el['Na']}")
check(values["type_cl"] == type_of_el["Cl"],
      f"results.json type_cl={values['type_cl']} != data file Cl type {type_of_el['Cl']}")
check(values["n_types"] == len(type_pos),
      f"results.json n_types={values['n_types']} != data file types {len(type_pos)}")

# ── Layer 4: L4-lite — the LAMMPS engine itself reads the data file ──────────
from lammps import lammps

lmp = lammps(cmdargs=["-log", "none", "-screen", "none"])
try:
    for cmd in ("units lj", "atom_style atomic", "boundary p p p"):
        lmp.command(cmd)
    lmp.command(f"read_data {os.path.join(WORKSPACE, 'nacl.data')}")
    lmp.command("mass * 1.0")
    lmp.command("pair_style zero 5.0")
    lmp.command("pair_coeff * *")
    lmp.command("run 0")
except Exception as e:
    fail(f"LAMMPS could not read/run nacl.data: {e}")

n_lmp = lmp.get_natoms()
check(n_lmp == len(ref),
      f"LAMMPS read {n_lmp} atoms from nacl.data (expected {len(ref)})")
box = lmp.extract_box()
# extract_box -> (boxlo[3], boxhi[3], xy, yz, xz, ...)
boxlo, boxhi = box[0], box[1]
for i, name in enumerate("xyz"):
    got = boxhi[i] - boxlo[i]
    check(abs(got - ref_len) <= CELL_TOL,
          f"LAMMPS box {name}-length {got:.6f} != CIF cell {ref_len} "
          f"(tol {CELL_TOL}) — data file box does not match the structure")

# ── Layer 5: Reference anchors ────────────────────────────────────────────────
check(values["n_atoms"] == refs["n_atoms_expected"],
      f"results.json n_atoms={values['n_atoms']} != {refs['n_atoms_expected']}")
check(abs(ref_len - refs["lattice_A_ref"]) <= CELL_TOL,
      f"CIF lattice {ref_len} != ref {refs['lattice_A_ref']} (asset mismatch?)")

print("PASS: ase-format-convert")

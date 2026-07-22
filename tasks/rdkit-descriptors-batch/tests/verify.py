#!/usr/bin/env python3
"""
Verifier for rdkit-descriptors-batch:
  0. ASSET INTEGRITY: sha256 of every asset pinned in refs.json must match
     the /workspace copy (agent-writable) before any check that reads it.
  1. File existence + results.json schema (values/units) + CSV header.
  2. REAL RECOMPUTE (natural L4): recompute canonical SMILES and all five
     descriptors for every input line with the in-image RDKit and compare
     the CSV row by row, in order (floats to 1e-4; ints and SMILES exact).
  3. Counts in results.json must match the recomputed values.
  4. Reference anchors (n_input, n_rows, MW sum) from calibration.
"""
import csv
import hashlib
import json
import sys
import os

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

# ── Layer 0: ASSET INTEGRITY — never trust the workspace copy ─────────────────
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

asset_hashes = refs.get("asset_hashes", {})
check(asset_hashes, "refs.json pins no asset_hashes — verifier must not trust workspace assets")
for rel_path, want_hash in asset_hashes.items():
    apath = os.path.join(WORKSPACE, rel_path)
    check(os.path.isfile(apath), f"pinned asset missing: {rel_path}")
    got_hash = _sha256(apath)
    check(got_hash == want_hash,
          f"asset {rel_path} was tampered with: sha256 {got_hash} != pinned {want_hash}")

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("descriptors.csv", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_input", "n_rows"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

with open(os.path.join(WORKSPACE, "descriptors.csv"), newline="") as f:
    reader = csv.reader(f)
    rows = list(reader)

check(rows, "descriptors.csv is empty")
check(rows[0] == ["canonical_smiles", "mw", "logp", "tpsa", "hbd", "hba"],
      f"descriptors.csv header must be exactly "
      f"canonical_smiles,mw,logp,tpsa,hbd,hba; got {rows[0]}")
data_rows = rows[1:]
check(all(len(r) == 6 for r in data_rows),
      "every data row in descriptors.csv must have 6 columns")

# ── Layer 2: REAL RECOMPUTE — recompute every descriptor ourselves ────────────
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, Lipinski, rdMolDescriptors

input_path = os.path.join(WORKSPACE, "assets", "input_smiles.txt")
with open(input_path) as f:
    input_lines = [l.strip() for l in f if l.strip()]

float_tol = refs["descriptor_tol"]
expected = []
for s in input_lines:
    mol = Chem.MolFromSmiles(s)
    check(mol is not None, f"input line not parseable by RDKit (asset corrupted?): {s!r}")
    expected.append((
        Chem.MolToSmiles(mol),
        float(Descriptors.MolWt(mol)),
        float(Crippen.MolLogP(mol)),
        float(rdMolDescriptors.CalcTPSA(mol)),
        int(Lipinski.NumHDonors(mol)),
        int(Lipinski.NumHAcceptors(mol)),
    ))

check(len(data_rows) == len(expected),
      f"descriptors.csv has {len(data_rows)} data rows (expected {len(expected)})")

for i, (got, want) in enumerate(zip(data_rows, expected), start=1):
    check(got[0] == want[0],
          f"row {i}: canonical_smiles {got[0]!r} != recomputed {want[0]!r}")
    for col, name in ((1, "mw"), (2, "logp"), (3, "tpsa")):
        try:
            gv = float(got[col])
        except ValueError:
            fail(f"row {i}: {name} value {got[col]!r} is not a float")
        check(abs(gv - want[col]) <= float_tol,
              f"row {i}: {name} {gv} != recomputed {want[col]:.6f} "
              f"(tol {float_tol}) — fabricated or wrong descriptor definition")
    for col, name in ((4, "hbd"), (5, "hba")):
        try:
            gv = int(got[col])
        except ValueError:
            fail(f"row {i}: {name} value {got[col]!r} is not an integer")
        check(gv == want[col],
              f"row {i}: {name} {gv} != recomputed {want[col]}")

# ── Layer 3: counts ────────────────────────────────────────────────────────────
check(values["n_input"] == len(input_lines),
      f"n_input={values['n_input']} != actual {len(input_lines)}")
check(values["n_rows"] == len(expected),
      f"n_rows={values['n_rows']} != actual {len(expected)}")

# ── Layer 4: reference anchors (calibrated) ───────────────────────────────────
check(values["n_input"] == refs["n_input_expected"],
      f"n_input={values['n_input']} != expected {refs['n_input_expected']}")
check(values["n_rows"] == refs["n_rows_expected"],
      f"n_rows={values['n_rows']} != expected {refs['n_rows_expected']}")
mw_sum = sum(e[1] for e in expected)
check(abs(mw_sum - refs["mw_sum_ref"]) <= refs["mw_sum_tol"],
      f"recomputed MW sum {mw_sum:.6f} outside ref {refs['mw_sum_ref']} "
      f"± {refs['mw_sum_tol']} (image drift?)")

print("PASS: rdkit-descriptors-batch")

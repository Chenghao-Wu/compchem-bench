#!/usr/bin/env python3
"""
Verifier for rdkit-mol-standardize:
  0. ASSET INTEGRITY: sha256 of messy.sdf (agent-writable) must match the
     pinned hash before any check that reads it.
  1. File existence + results.json schema (values/units).
  2. REAL RECOMPUTE (natural L4): replay the pinned standardization recipe
     (SDMolSupplier -> LargestFragmentChooser -> Uncharger -> canonical
     isomeric SMILES -> dedup) and compare the submitted set exactly;
     standardized.smi must additionally be sorted, one SMILES per line.
  3. Counts in results.json must match the replayed counts.
  4. Reference anchors (calibrated counts).
"""
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
for fname in ("standardized.smi", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_input", "n_parsed", "n_failed", "n_unique"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: REAL RECOMPUTE — replay the pinned recipe ────────────────────────
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

suppl = Chem.SDMolSupplier(os.path.join(WORKSPACE, "assets", "messy.sdf"))
chooser = rdMolStandardize.LargestFragmentChooser()
uncharger = rdMolStandardize.Uncharger()

n_input, n_parsed, n_failed = 0, 0, 0
canon = []
for mol in suppl:
    n_input += 1
    if mol is None:
        n_failed += 1
        continue
    n_parsed += 1
    frag = chooser.choose(mol)
    neu = uncharger.uncharge(frag)
    canon.append(Chem.MolToSmiles(neu))

expected = sorted(set(canon))

with open(os.path.join(WORKSPACE, "standardized.smi")) as f:
    submitted = [l.strip() for l in f if l.strip()]

check(submitted == sorted(submitted),
      "standardized.smi must be sorted lexicographically, one SMILES per line")
check(len(submitted) == len(set(submitted)),
      "standardized.smi contains duplicate entries")
check(submitted == expected,
      f"standardized.smi set does not match the replayed recipe:\n"
      f"  only in submission: {sorted(set(submitted) - set(expected))}\n"
      f"  only in recompute:  {sorted(set(expected) - set(submitted))}")

# ── Layer 3: counts ────────────────────────────────────────────────────────────
check(values["n_input"] == n_input,
      f"n_input={values['n_input']} != replayed {n_input}")
check(values["n_parsed"] == n_parsed,
      f"n_parsed={values['n_parsed']} != replayed {n_parsed}")
check(values["n_failed"] == n_failed,
      f"n_failed={values['n_failed']} != replayed {n_failed}")
check(values["n_unique"] == len(expected),
      f"n_unique={values['n_unique']} != replayed {len(expected)}")

# ── Layer 4: reference anchors (calibrated counts) ────────────────────────────
for key in ("n_input", "n_parsed", "n_failed", "n_unique"):
    check(values[key] == refs[f"{key}_expected"],
          f"{key}={values[key]} != expected {refs[f'{key}_expected']} (image drift?)")

print("PASS: rdkit-mol-standardize")

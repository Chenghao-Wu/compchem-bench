#!/usr/bin/env python3
"""
Verifier for rdkit-reaction-enumerate:
  0. ASSET INTEGRITY: sha256 of reaction.smirks and building_blocks.csv
     (agent-writable) must match the pinned hashes.
  1. File existence + results.json schema (values/units).
  2. REAL RECOMPUTE (natural L4): replay the full pinned pipeline
     (ReactionFromSmarts -> RunReactants over the acid x amine cross product
     -> sanitize -> InChIKey dedup -> MW/rotatable filter) and compare the
     submitted kept set exactly, stereochemistry included; products.smi must
     additionally be sorted with no duplicates.
  3. All five counts must match the replayed counts exactly.
  4. Reference anchors (calibrated counts).
"""
import csv
import hashlib
import json
import sys
import os

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

MW_MIN, MW_MAX, MAX_ROT = 150.0, 350.0, 8


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
for fname in ("products.smi", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

COUNT_KEYS = ("n_pairs", "n_raw_products", "n_failed_sanitize", "n_unique", "n_kept")
for key in COUNT_KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: REAL RECOMPUTE — replay the full pinned pipeline ─────────────────
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.rdChemReactions import ReactionFromSmarts

with open(os.path.join(WORKSPACE, "assets", "reaction.smirks")) as f:
    rxn = ReactionFromSmarts(f.read().strip())
rxn.Initialize()
check(rxn.GetNumReactantTemplates() == 2, "reaction must have 2 reactant templates")

acids, amines = [], []
with open(os.path.join(WORKSPACE, "assets", "building_blocks.csv")) as f:
    for row in csv.DictReader(f):
        mol = Chem.MolFromSmiles(row["smiles"])
        check(mol is not None, f"unparseable building block (asset corrupted?): {row}")
        (acids if row["role"] == "acid" else amines).append(mol)

re_pairs = 0
raw = []
for acid in acids:
    for amine in amines:
        re_pairs += 1
        for product_tuple in rxn.RunReactants((acid, amine)):
            raw.extend(product_tuple)

ok, re_failed = [], 0
for p in raw:
    try:
        p.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(p)
    except Exception:
        re_failed += 1
        continue
    ok.append(p)

seen, uniq = set(), []
for p in ok:
    ik = Chem.MolToInchiKey(p)
    if ik not in seen:
        seen.add(ik)
        uniq.append(p)

kept = [p for p in uniq
        if MW_MIN <= Descriptors.MolWt(p) <= MW_MAX
        and rdMolDescriptors.CalcNumRotatableBonds(p) <= MAX_ROT]
expected = sorted(Chem.MolToSmiles(p) for p in kept)

with open(os.path.join(WORKSPACE, "products.smi")) as f:
    submitted = [l.strip() for l in f if l.strip()]

check(submitted == sorted(submitted),
      "products.smi must be sorted lexicographically, one SMILES per line")
check(len(submitted) == len(set(submitted)),
      "products.smi contains duplicate entries")
check(submitted == expected,
      f"products.smi does not match the replayed pipeline:\n"
      f"  only in submission: {sorted(set(submitted) - set(expected))}\n"
      f"  only in recompute:  {sorted(set(expected) - set(submitted))}")

# ── Layer 3: counts ────────────────────────────────────────────────────────────
check(values["n_pairs"] == re_pairs,
      f"n_pairs={values['n_pairs']} != replayed {re_pairs}")
check(values["n_raw_products"] == len(raw),
      f"n_raw_products={values['n_raw_products']} != replayed {len(raw)}")
check(values["n_failed_sanitize"] == re_failed,
      f"n_failed_sanitize={values['n_failed_sanitize']} != replayed {re_failed}")
check(values["n_unique"] == len(uniq),
      f"n_unique={values['n_unique']} != replayed {len(uniq)}")
check(values["n_kept"] == len(kept),
      f"n_kept={values['n_kept']} != replayed {len(kept)}")

# ── Layer 4: reference anchors (calibrated counts) ────────────────────────────
for key in COUNT_KEYS:
    check(values[key] == refs[f"{key}_expected"],
          f"{key}={values[key]} != expected {refs[f'{key}_expected']} (image drift?)")

print("PASS: rdkit-reaction-enumerate")

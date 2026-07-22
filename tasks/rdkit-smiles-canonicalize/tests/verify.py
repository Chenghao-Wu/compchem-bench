#!/usr/bin/env python3
"""
Verifier for rdkit-smiles-canonicalize:
  0. ASSET INTEGRITY: every asset pinned in refs.json "asset_hashes" must
     match its sha256 in /workspace — the agent can write /workspace/assets,
     so the verifier never trusts the workspace copy without this check.
  1. File existence + results.json schema (values/units)
  2. REAL RECOMPUTE: recompute the canonical isomeric SMILES of every
     input line with RDKit and compare against canonical.smi exactly,
     line by line (order included). Counts in results.json must match
     the recomputed values.
  There is no tolerance and no fallback: canonicalization is exact.
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
# /workspace/assets is agent-writable; the recompute below reads from it, so
# any asset this verifier relies on must be pinned by hash in refs.json.
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
for fname in ("canonical.smi", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_input", "n_valid", "n_unique"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: REAL RECOMPUTE — canonicalize every input line ourselves ─────────
from rdkit import Chem

input_path = os.path.join(WORKSPACE, "assets", "input_smiles.txt")
check(os.path.isfile(input_path), "assets/input_smiles.txt missing from image")

with open(input_path) as f:
    input_lines = [l.strip() for l in f if l.strip()]

expected = []
for s in input_lines:
    mol = Chem.MolFromSmiles(s)
    check(mol is not None, f"input line not parseable by RDKit (asset corrupted?): {s!r}")
    expected.append(Chem.MolToSmiles(mol))

with open(os.path.join(WORKSPACE, "canonical.smi")) as f:
    submitted = [l.strip() for l in f if l.strip()]

check(len(submitted) == len(expected),
      f"canonical.smi has {len(submitted)} entries (expected {len(expected)})")

for i, (got, want) in enumerate(zip(submitted, expected), start=1):
    check(got == want,
          f"canonical.smi line {i}: {got!r} != recomputed canonical SMILES {want!r} "
          f"(input was {input_lines[i-1]!r})")

# ── Layer 3: counts ────────────────────────────────────────────────────────────
check(values["n_input"] == len(input_lines),
      f"n_input={values['n_input']} != actual {len(input_lines)}")
check(values["n_valid"] == len(expected),
      f"n_valid={values['n_valid']} != actual {len(expected)}")
check(values["n_unique"] == len(set(expected)),
      f"n_unique={values['n_unique']} != actual {len(set(expected))}")

# ── Layer 4: reference sanity (calibrated counts) ─────────────────────────────
check(values["n_input"] == refs["n_input_expected"],
      f"n_input={values['n_input']} != expected {refs['n_input_expected']}")
check(values["n_unique"] == refs["n_unique_expected"],
      f"n_unique={values['n_unique']} != expected {refs['n_unique_expected']}")

print("PASS: rdkit-smiles-canonicalize")

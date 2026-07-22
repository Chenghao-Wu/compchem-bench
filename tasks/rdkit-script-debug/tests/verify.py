#!/usr/bin/env python3
"""
Verifier for rdkit-script-debug:
  0. ASSET INTEGRITY: sha256 of assets/analyze_mols.py (broken original) and
     assets/input.smi (agent-writable) must match the pinned hashes.
  1. File existence (fixed /workspace/analyze_mols.py, mols.smi,
     results.json) + results.json schema.
  2. REAL RERUN (natural L4): delete mols.smi/results.json and re-run the
     agent's fixed script — a non-zero exit is a hard fail — then use only
     the outputs IT regenerates.
  3. REAL RECOMPUTE: independently replay the intended pipeline (parse with
     sanitization, skip None, rdMolStandardize.Cleanup, canonical SMILES,
     MolWt) from assets/input.smi and compare mols.smi line by line and
     results.json values (counts exact, mw_mean to 1e-4).
  4. Reference anchors (calibrated counts + mw_mean).
"""
import hashlib
import json
import subprocess
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

# ── Layer 1: File existence ────────────────────────────────────────────────────
for fname in ("analyze_mols.py", "mols.smi", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

# ── Layer 2: REAL RERUN of the fixed script ───────────────────────────────────
for fname in ("mols.smi", "results.json"):
    os.remove(os.path.join(WORKSPACE, fname))  # force the script to regenerate them

proc = subprocess.run(
    [sys.executable, "analyze_mols.py"],
    cwd=WORKSPACE, capture_output=True, text=True, timeout=120,
)
check(proc.returncode == 0,
      f"analyze_mols.py exited with code {proc.returncode} — the script is not fixed:\n"
      f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
for fname in ("mols.smi", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)),
          f"analyze_mols.py ran but did not produce {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_input", "n_parsed", "n_failed", "mw_mean"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

with open(os.path.join(WORKSPACE, "mols.smi")) as f:
    submitted_smi = [l.strip() for l in f if l.strip()]

# ── Layer 3: REAL RECOMPUTE — independent reference implementation ────────────
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize

with open(os.path.join(WORKSPACE, "assets", "input.smi")) as f:
    input_lines = [l.strip() for l in f if l.strip()]

re_mws, re_canon, re_failed = [], [], 0
for s in input_lines:
    mol = Chem.MolFromSmiles(s)
    if mol is None:
        re_failed += 1
        continue
    mol = rdMolStandardize.Cleanup(mol)
    re_mws.append(float(Descriptors.MolWt(mol)))
    re_canon.append(Chem.MolToSmiles(mol))
re_parsed = len(re_mws)
re_mw_mean = sum(re_mws) / re_parsed

check(submitted_smi == re_canon,
      f"mols.smi does not match the replayed pipeline:\n"
      f"  submitted: {submitted_smi}\n  recomputed: {re_canon}")
check(values["n_input"] == len(input_lines),
      f"n_input={values['n_input']} != actual {len(input_lines)}")
check(values["n_parsed"] == re_parsed,
      f"n_parsed={values['n_parsed']} != recomputed {re_parsed}")
check(values["n_failed"] == re_failed,
      f"n_failed={values['n_failed']} != recomputed {re_failed}")
mw_tol = refs["mw_mean_tol"]
check(abs(values["mw_mean"] - re_mw_mean) <= mw_tol,
      f"mw_mean={values['mw_mean']:.6f} != recomputed {re_mw_mean:.6f} g/mol "
      f"(tol {mw_tol})")

# ── Layer 4: reference anchors (calibrated) ───────────────────────────────────
check(values["n_parsed"] == refs["n_parsed_expected"],
      f"n_parsed={values['n_parsed']} != expected {refs['n_parsed_expected']}")
check(values["n_failed"] == refs["n_failed_expected"],
      f"n_failed={values['n_failed']} != expected {refs['n_failed_expected']}")
check(abs(re_mw_mean - refs["mw_mean_ref"]) <= refs["mw_mean_ref_tol"],
      f"recomputed mw_mean {re_mw_mean:.6f} outside ref {refs['mw_mean_ref']} "
      f"± {refs['mw_mean_ref_tol']} (image drift?)")

print("PASS: rdkit-script-debug")

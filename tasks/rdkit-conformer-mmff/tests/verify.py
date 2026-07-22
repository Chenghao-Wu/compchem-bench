#!/usr/bin/env python3
"""
Verifier for rdkit-conformer-mmff:
  1. File existence + results.json schema (values/units)
  2. Molecular identity: the SDF must contain the target molecule
     (canonical SMILES match)
  3. REAL RECOMPUTE (cross-verify):
     a. recompute the MMFF94 energy of the submitted conformer — must
        equal the reported energy;
     b. RE-OPTIMIZE the submitted conformer with MMFF94 — the energy must
        not drop (proves the structure is a true MMFF minimum, not an
        embedded-but-unoptimized or hand-built geometry);
     c. descriptors (rotatable bonds, heavy atoms) recomputed — must
        equal the reported values;
  4. Reference tolerance: recomputed energy vs the calibrated reference
     energy for the pinned-seed conformer.
  Any anomaly is a hard fail.
"""
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

# ── Layer 0: ASSET INTEGRITY — never trust the workspace copy ────────────────
# /workspace/assets is agent-writable; any asset this verifier relies on is
# pinned by sha256 in refs.json (P2 asset-integrity convention).
import hashlib

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
for fname in ("conformer.sdf", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("mmff_energy", "n_rotatable_bonds", "n_heavy_atoms"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Molecular identity ────────────────────────────────────────────────
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

suppl = Chem.SDMolSupplier(os.path.join(WORKSPACE, "conformer.sdf"), removeHs=False)
mols = [m for m in suppl if m is not None]
check(len(mols) >= 1, "conformer.sdf contains no parseable molecule")
mol = mols[0]
check(mol.GetNumConformers() >= 1, "Submitted molecule has no 3D conformer")

with open(os.path.join(WORKSPACE, "assets", "target.smi")) as f:
    target_smiles = f.read().strip()
target = Chem.MolFromSmiles(target_smiles)

# Stereo-insensitive identity check: embedding assigns 3D stereochemistry,
# which would make an isomeric comparison spuriously fail.
submitted_can = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=False)
target_can = Chem.MolToSmiles(target, isomericSmiles=False)
check(submitted_can == target_can,
      f"Submitted molecule {submitted_can!r} is not the target {target_can!r}")

check(mol.GetNumAtoms() == Chem.AddHs(target).GetNumAtoms(),
      f"Submitted molecule has {mol.GetNumAtoms()} atoms; expected "
      f"{Chem.AddHs(target).GetNumAtoms()} (explicit Hs)")

# ── Layer 3: REAL RECOMPUTE ────────────────────────────────────────────────────
props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
ff = AllChem.MMFFGetMoleculeForceField(mol, props)
check(ff is not None, "Could not build MMFF94 force field for submitted molecule "
                      "(missing MMFF parameters?)")
e_submitted = float(ff.CalcEnergy())

# (a) reported energy must equal the recomputed energy of the submitted geometry
e_rep = values["mmff_energy"]
e_self_tol = refs["crossverify_energy_tol_kcal"]
check(abs(e_submitted - e_rep) <= e_self_tol,
      f"reported mmff_energy {e_rep:.6f} != recomputed energy of submitted "
      f"conformer {e_submitted:.6f} kcal/mol (tol {e_self_tol})")

# (b) re-optimize: a true MMFF minimum must not relax further
e_drop_tol = refs["reopt_max_energy_drop_kcal"]
e_before = e_submitted
AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94")
ff2 = AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94"))
e_after = float(ff2.CalcEnergy())
check(e_before - e_after <= e_drop_tol,
      f"Re-optimization lowered the MMFF energy by {e_before - e_after:.4f} kcal/mol "
      f"(allowed {e_drop_tol}) — submitted conformer is NOT an MMFF-optimized minimum")

# (c) descriptors recomputed
n_rot = int(Descriptors.NumRotatableBonds(mol))
n_heavy = int(mol.GetNumHeavyAtoms())
check(n_rot == values["n_rotatable_bonds"],
      f"n_rotatable_bonds reported {values['n_rotatable_bonds']} != recomputed {n_rot}")
check(n_heavy == values["n_heavy_atoms"],
      f"n_heavy_atoms reported {values['n_heavy_atoms']} != recomputed {n_heavy}")

# ── Layer 4: Reference tolerance (pinned-seed conformer energy) ───────────────
e_ref = refs["mmff_energy_ref_kcal"]
e_tol = refs["mmff_energy_tol_kcal"]
check(abs(e_submitted - e_ref) <= e_tol,
      f"MMFF energy {e_submitted:.6f} kcal/mol differs from ref {e_ref:.6f} "
      f"by >{e_tol} — conformer was not generated with the pinned ETKDG seed")

print("PASS: rdkit-conformer-mmff")

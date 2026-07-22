#!/usr/bin/env python3
"""
Verifier for rdkit-conformer-cluster:
  0. ASSET INTEGRITY: sha256 of assets/target.smi (agent-writable) must
     match the pinned hash.
  1. File existence + results.json schema (values/units).
  2. Molecular identity: every SDF record is the target molecule with a 3D
     conformer and explicit Hs.
  3. REAL RECOMPUTE (L4):
     a. recompute the MMFF94 energy of every submitted conformer — the
        reported min must equal the recomputed min;
     b. RE-OPTIMIZE every conformer with MMFF94 — the energy must not drop
        (proves each is a true MMFF minimum, not an embedded-but-
        unoptimized or hand-built geometry);
     c. re-assemble the ensemble from the SDF, recompute the best-fit RMSD
        matrix and re-cluster with the pinned Butina settings — n_clusters
        and n_largest_cluster must equal the reported values.
  4. Reference regeneration: regenerate the ensemble from the pinned
     ETKDGv3 seed and match every conformer energy in order (proves the
     exact pinned pipeline), plus calibrated min-energy / cluster-count
     anchors.
  Any anomaly is a hard fail.
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
for fname in ("conformers.sdf", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_conformers", "n_clusters", "n_largest_cluster", "min_mmff_energy"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Molecular identity ────────────────────────────────────────────────
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.ML.Cluster import Butina

with open(os.path.join(WORKSPACE, "assets", "target.smi")) as f:
    target_smiles = f.read().strip()
target = Chem.MolFromSmiles(target_smiles)
target_can = Chem.MolToSmiles(target, isomericSmiles=False)
n_atoms_exp = Chem.AddHs(target).GetNumAtoms()

suppl = Chem.SDMolSupplier(os.path.join(WORKSPACE, "conformers.sdf"), removeHs=False)
records = [m for m in suppl if m is not None]
check(len(records) == values["n_conformers"],
      f"conformers.sdf has {len(records)} parseable records but "
      f"n_conformers={values['n_conformers']}")
check(len(records) == refs["n_conformers_expected"],
      f"conformers.sdf has {len(records)} records (expected "
      f"{refs['n_conformers_expected']})")

for i, m in enumerate(records):
    check(m.GetNumConformers() >= 1, f"record {i + 1} has no 3D conformer")
    can = Chem.MolToSmiles(Chem.RemoveHs(m), isomericSmiles=False)
    check(can == target_can,
          f"record {i + 1}: molecule {can!r} is not the target {target_can!r}")
    check(m.GetNumAtoms() == n_atoms_exp,
          f"record {i + 1}: {m.GetNumAtoms()} atoms, expected {n_atoms_exp} "
          f"(explicit Hs)")

# ── Layer 3: REAL RECOMPUTE ────────────────────────────────────────────────────
e_self_tol = refs["crossverify_energy_tol_kcal"]
reopt_tol = refs["reopt_max_energy_drop_kcal"]

rec_e = []
for i, m in enumerate(records):
    props = AllChem.MMFFGetMoleculeProperties(m, mmffVariant="MMFF94")
    ff = AllChem.MMFFGetMoleculeForceField(m, props)
    check(ff is not None,
          f"record {i + 1}: cannot build MMFF94 force field (missing parameters?)")
    e0 = float(ff.CalcEnergy())
    rec_e.append(e0)

# (a) reported minimum must equal the recomputed minimum of the submission
check(abs(min(rec_e) - values["min_mmff_energy"]) <= e_self_tol,
      f"reported min_mmff_energy {values['min_mmff_energy']:.6f} != recomputed "
      f"minimum of submitted ensemble {min(rec_e):.6f} kcal/mol (tol {e_self_tol})")

# (b) re-optimize: true MMFF minima must not relax further
for i, m in enumerate(records):
    e0 = rec_e[i]
    AllChem.MMFFOptimizeMolecule(m, mmffVariant="MMFF94", maxIters=2000)
    props = AllChem.MMFFGetMoleculeProperties(m, mmffVariant="MMFF94")
    e1 = float(AllChem.MMFFGetMoleculeForceField(m, props).CalcEnergy())
    check(e0 - e1 <= reopt_tol,
          f"record {i + 1}: re-optimization lowered the MMFF energy by "
          f"{e0 - e1:.4f} kcal/mol (allowed {reopt_tol}) — conformer is NOT an "
          f"MMFF-optimized minimum")

# (c) re-assemble the ensemble from the SDF and re-cluster
amol = Chem.Mol(records[0])
while amol.GetNumConformers() > 1:
    amol.RemoveConformer(1)
for m in records[1:]:
    amol.AddConformer(Chem.Conformer(m.GetConformer()), assignId=True)
dmat = AllChem.GetConformerRMSMatrix(amol, prealigned=False)
clusters = Butina.ClusterData(dmat, amol.GetNumConformers(), 1.0,
                              isDistData=True, reordering=True)
check(len(clusters) == values["n_clusters"],
      f"reported n_clusters={values['n_clusters']} != re-clustered "
      f"{len(clusters)} from the submitted conformers")
check(max(len(c) for c in clusters) == values["n_largest_cluster"],
      f"reported n_largest_cluster={values['n_largest_cluster']} != re-clustered "
      f"{max(len(c) for c in clusters)}")

# ── Layer 4: Reference regeneration from the pinned seed ──────────────────────
ref_mol = Chem.AddHs(Chem.MolFromSmiles(target_smiles))
params = AllChem.ETKDGv3()
params.randomSeed = 0xF00D
ref_ids = AllChem.EmbedMultipleConfs(ref_mol, numConfs=50, params=params)
check(len(ref_ids) == refs["n_conformers_expected"],
      f"reference regeneration embedded {len(ref_ids)} conformers (image drift?)")
AllChem.MMFFOptimizeMoleculeConfs(ref_mol, mmffVariant="MMFF94", numThreads=1,
                                  maxIters=2000)
ref_props = AllChem.MMFFGetMoleculeProperties(ref_mol, mmffVariant="MMFF94")
ref_e = [float(AllChem.MMFFGetMoleculeForceField(ref_mol, ref_props, confId=c).CalcEnergy())
         for c in ref_ids]

check(len(rec_e) == len(ref_e),
      f"submitted {len(rec_e)} conformers vs regenerated {len(ref_e)}")
per_conf_tol = refs["per_conformer_energy_tol_kcal"]
for i, (got, want) in enumerate(zip(rec_e, ref_e)):
    check(abs(got - want) <= per_conf_tol,
          f"conformer {i}: submitted energy {got:.6f} != regenerated reference "
          f"{want:.6f} kcal/mol (tol {per_conf_tol}) — ensemble was not produced "
          f"by the pinned ETKDG seed + MMFF94 pipeline")

e_ref = refs["min_energy_ref_kcal"]
e_tol = refs["min_energy_tol_kcal"]
check(abs(min(ref_e) - e_ref) <= e_tol,
      f"regenerated min energy {min(ref_e):.6f} outside ref {e_ref} ± {e_tol} "
      f"(image drift?)")
check(len(clusters) == refs["n_clusters_expected"],
      f"re-clustered n_clusters={len(clusters)} != expected "
      f"{refs['n_clusters_expected']} (image drift?)")

print("PASS: rdkit-conformer-cluster")

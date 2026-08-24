#!/usr/bin/env python3
"""
Verifier for ase-peo-md-equilibration (open-ended, seed-agnostic):
  0. ASSET INTEGRITY: sha256 of assets/peo_ff.py (agent-writable) must match
     the pinned hash — the force field defines the physics being graded.
  1. File existence + results.json schema (values/units).
  2. CHAIN REGENERATION: rebuild the PEO chain with the pinned RDKit pipeline
     (deterministic per version+seed) and require chain_init.xyz to match it.
  3. PROTOCOL: md.traj must satisfy the sampling protocol — first frame ==
     chain_init.xyz, enough integration steps and frames, regular saving at
     the required density, and (via the reported n_steps) a consistent
     average spacing.
  4. SELF-CONSISTENCY: recompute every Rg statistic and the equilibration
     verdict from the trajectory positions; require results.json to agree,
     require the production ensemble to meet the task's equilibration
     criterion, and require real Rg fluctuations (a thermalized coil
     breathes — a frozen or cosmetically shaken geometry stream does not).
  5. GENUINE EVOLUTION: the chain must have moved far from its starting
     geometry by the last frame. A real Langevin trajectory of this length
     displaces every atom by several Å; a fabricated wiggle does not.
  6. EQUILIBRIUM-ENSEMBLE INTERVALS (seed-agnostic): recomputed production
     statistics (mean Rg, Rg std, final FF energy recomputed with the
     integrity-checked force field) must fall within calibrated intervals.
     Any faithful 500 K sampling lands inside; short/unrelaxed/forged
     trajectories fall outside.

Any anomaly is a hard fail — there is no warning fallback.
"""
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

# ── Pinned contract constants (must match instruction.md) ────────────────────
N_MONOMERS = 10
EMBED_SEED = 0xf00d
TEMPERATURE_K = 500.0
MAX_SPACING = 10_000            # max saved-frame spacing (steps)
MIN_FRAMES = 200                # min saved frames
MIN_STEPS = 600_000             # min integration steps
DRIFT_THRESHOLD = 0.10          # equilibration criterion
UNRELAXED_FRAC = 0.03           # production mean must differ from Rg_init


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

spec = importlib.util.spec_from_file_location(
    "peo_ff", os.path.join(WORKSPACE, "assets", "peo_ff.py"))
peo_ff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peo_ff)

# ── Layer 1: File existence + schema ──────────────────────────────────────────
for fname in ("chain_init.xyz", "md.traj", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing file: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

REQUIRED = ("n_frames", "n_steps", "rg_initial", "rg_mean", "rg_std",
            "rg_drift_frac", "equilibrated", "final_energy")
for key in REQUIRED:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: CHAIN REGENERATION (pinned RDKit pipeline is deterministic) ──────
from rdkit import Chem
from rdkit.Chem import AllChem
from ase import Atoms
from ase.io import read

mol = Chem.MolFromSmiles("O" + "CCO" * N_MONOMERS)
mol = Chem.AddHs(mol)
params = AllChem.ETKDGv3()
params.randomSeed = EMBED_SEED
check(AllChem.EmbedMolecule(mol, params) == 0, "reference ETKDG embedding failed")
AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=2000)
mol = Chem.RemoveHs(mol)
ref_bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx()) for b in mol.GetBonds()]
ref_symbols = [a.GetSymbol() for a in mol.GetAtoms()]
ref_init = Atoms(symbols=ref_symbols, positions=mol.GetConformer().GetPositions())

def radius_of_gyration(frame):
    m = frame.get_masses()
    com = np.sum(frame.positions * m[:, None], axis=0) / m.sum()
    return float(np.sqrt(np.sum(m * np.sum((frame.positions - com) ** 2,
                                            axis=1)) / m.sum()))

n_atoms_exp = refs["n_atoms_expected"]
check(len(ref_init) == n_atoms_exp,
      f"internal error: regenerated chain has {len(ref_init)} atoms, expected {n_atoms_exp}")

init_submitted = read(os.path.join(WORKSPACE, "chain_init.xyz"))
check(len(init_submitted) == n_atoms_exp,
      f"chain_init.xyz has {len(init_submitted)} atoms, expected {n_atoms_exp}")
check(init_submitted.get_chemical_symbols() == ref_symbols,
      "chain_init.xyz element order does not match the pinned PEO chain "
      "(O" + "CCO" * N_MONOMERS + " construction)")
pos_diff = float(np.max(np.abs(init_submitted.positions - ref_init.positions)))
check(pos_diff <= refs["init_pos_tol_A"],
      f"chain_init.xyz positions differ from the regenerated pinned chain by "
      f"up to {pos_diff:.2e} Å (tol {refs['init_pos_tol_A']}) — wrong "
      f"construction pipeline (SMILES/embedding seed/MMFF94/RemoveHs)?")

rg_initial_file = radius_of_gyration(init_submitted)
check(abs(rg_initial_file - values["rg_initial"]) <= refs["recompute_rg_tol_A"],
      f"reported rg_initial {values['rg_initial']:.6f} Å != Rg of chain_init.xyz "
      f"{rg_initial_file:.6f} Å")

# ── Layer 3: PROTOCOL ─────────────────────────────────────────────────────────
traj = read(os.path.join(WORKSPACE, "md.traj"), index=":")
n_frames = len(traj)
check(n_frames >= MIN_FRAMES,
      f"md.traj has {n_frames} frames; the sampling protocol requires >= {MIN_FRAMES}")
check(values["n_frames"] == n_frames,
      f"reported n_frames {values['n_frames']} != actual frame count {n_frames}")
n_steps = values["n_steps"]
check(isinstance(n_steps, int) and n_steps >= MIN_STEPS,
      f"reported n_steps {n_steps} < minimum {MIN_STEPS} integration steps")
avg_spacing = n_steps / max(n_frames - 1, 1)
check(avg_spacing <= MAX_SPACING * 1.02,
      f"average saved-frame spacing {avg_spacing:.0f} steps exceeds the "
      f"allowed {MAX_SPACING} (n_steps={n_steps}, n_frames={n_frames})")

for k, frame in enumerate(traj):
    check(len(frame) == n_atoms_exp,
          f"frame {k} has {len(frame)} atoms, expected {n_atoms_exp}")
    check(frame.get_chemical_symbols() == ref_symbols,
          f"frame {k} element order differs from the pinned chain")
    check(np.all(np.isfinite(frame.positions)), f"frame {k} has non-finite positions")

f0_diff = float(np.max(np.abs(traj[0].positions - init_submitted.positions)))
check(f0_diff <= refs["init_pos_tol_A"],
      f"md.traj frame 0 differs from chain_init.xyz by up to {f0_diff:.2e} Å — "
      f"the trajectory must start from the submitted initial chain")

# ── Layer 4: SELF-CONSISTENCY + criterion + fluctuations ─────────────────────
rg_series = np.array([radius_of_gyration(fr) for fr in traj])
production = rg_series[n_frames // 2:]
b1 = production[: len(production) // 2]
b2 = production[-len(production) // 2:]
rg_mean_re = float(production.mean())
rg_std_re = float(production.std())
drift_re = abs(b2.mean() - b1.mean()) / b2.mean()

rtol = refs["recompute_rg_tol_A"]
check(abs(rg_mean_re - values["rg_mean"]) <= rtol,
      f"reported rg_mean {values['rg_mean']:.6f} != recomputed {rg_mean_re:.6f} Å")
check(abs(rg_std_re - values["rg_std"]) <= rtol,
      f"reported rg_std {values['rg_std']:.6f} != recomputed {rg_std_re:.6f} Å")
check(abs(drift_re - values["rg_drift_frac"]) <= refs["recompute_drift_tol"],
      f"reported rg_drift_frac {values['rg_drift_frac']:.6f} != recomputed {drift_re:.6f}")

unrelaxed_re = abs(rg_mean_re - rg_initial_file) >= UNRELAXED_FRAC * rg_initial_file
equilibrated_re = bool(drift_re < DRIFT_THRESHOLD and unrelaxed_re)
check(bool(values["equilibrated"]) == equilibrated_re,
      f"reported equilibrated={values['equilibrated']} inconsistent with the "
      f"recomputed drift {drift_re:.5f} / relaxation check")
check(equilibrated_re,
      f"the simulation is NOT equilibrated by the task criterion: "
      f"drift={drift_re:.5f} (threshold {DRIFT_THRESHOLD}), "
      f"|rg_mean - rg_initial|/rg_initial = "
      f"{abs(rg_mean_re - rg_initial_file) / rg_initial_file:.5f} "
      f"(required >= {UNRELAXED_FRAC})")

check(rg_std_re >= refs["rg_std_min_A"],
      f"production-ensemble Rg std {rg_std_re:.4f} Å < floor "
      f"{refs['rg_std_min_A']} Å — a thermalized coil breathes; a frozen or "
      f"cosmetically shaken geometry stream does not")

# ── Layer 5: GENUINE EVOLUTION (defeats fabricated wiggle trajectories) ───────
disp = np.linalg.norm(traj[-1].positions - traj[0].positions, axis=1)
check(float(disp.min()) >= refs["min_last_frame_displacement_A"],
      f"smallest first→last-frame atom displacement {disp.min():.3f} Å < "
      f"{refs['min_last_frame_displacement_A']} Å — the chain did not genuinely "
      f"evolve (fabricated or frozen trajectory?)")

# ── Layer 6: EQUILIBRIUM-ENSEMBLE INTERVALS (seed-agnostic) ──────────────────
ref_init.calc = peo_ff.make_calculator(ref_init, ref_bonds)
last = Atoms(symbols=ref_symbols, positions=traj[-1].positions)
last.calc = ref_init.calc
e_re = float(last.get_potential_energy())
check(abs(e_re - values["final_energy"]) <= refs["recompute_energy_tol_eV"],
      f"reported final_energy {values['final_energy']:.6f} eV != recomputed "
      f"pinned-FF energy of the final frame {e_re:.6f} eV")

check(abs(rg_mean_re - refs["rg_mean_ref_A"]) <= refs["rg_mean_tol_A"],
      f"production mean Rg {rg_mean_re:.4f} Å outside the equilibrium "
      f"interval around {refs['rg_mean_ref_A']:.4f} Å (tol "
      f"{refs['rg_mean_tol_A']}) — the sampled ensemble is not the 500 K "
      f"equilibrium ensemble")
check(abs(rg_std_re - refs["rg_std_ref_A"]) <= refs["rg_std_tol_A"],
      f"production Rg std {rg_std_re:.4f} Å outside the equilibrium interval "
      f"around {refs['rg_std_ref_A']:.4f} Å (tol {refs['rg_std_tol_A']})")
check(refs["final_energy_min_eV"] <= e_re <= refs["final_energy_max_eV"],
      f"final-frame FF energy {e_re:.4f} eV outside the equilibrium range "
      f"[{refs['final_energy_min_eV']}, {refs['final_energy_max_eV']}] eV — "
      f"the final structure is not a thermalized 500 K configuration")

print("PASS: ase-peo-md-equilibration")

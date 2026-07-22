#!/usr/bin/env python3
"""
Verifier for ase-neb-adatom:
  0. ASSET INTEGRITY: the relaxed endpoints are the NEB ground truth and
     live in agent-writable /workspace/assets — validate pinned sha256.
  1. File existence + results.json schema (values/units)
  2. Band integrity: 7 frames, 37 Cu atoms, endpoint frames reproduce the
     provided structures, interior frames actually move the adatom
  3. L4 REAL RECOMPUTE: EMT energy of EVERY frame from the geometries —
     endpoints degenerate, max-energy frame interior, barrier derived from
     the band itself must match results.json, and the saddle frame's
     recomputed forces prove a converged climbing image (an un-optimized
     interpolation has large forces even when energies are honestly
     reported).
  4. Reference anchors (barrier vs calibrated value).
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
for fname in ("neb_band.traj", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("barrier", "n_images", "saddle_fmax"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Band integrity ───────────────────────────────────────────────────
from ase.io import read

band = read(os.path.join(WORKSPACE, "neb_band.traj"), index=":")
n_expected = refs["n_images_expected"]
check(len(band) == n_expected,
      f"neb_band.traj has {len(band)} frames (expected {n_expected})")
check(values["n_images"] == n_expected,
      f"results.json n_images={values['n_images']} != {n_expected}")

ep_i = read(os.path.join(WORKSPACE, "assets", "initial.xyz"))
ep_f = read(os.path.join(WORKSPACE, "assets", "final.xyz"))
n_atoms = len(ep_i)
check(n_atoms == refs["n_atoms_expected"],
      f"endpoint asset has {n_atoms} atoms (expected {refs['n_atoms_expected']})")

ep_cell = np.array(ep_i.cell)
for k, frame in enumerate(band):
    check(len(frame) == n_atoms,
          f"frame {k} has {len(frame)} atoms (expected {n_atoms})")
    check(set(frame.get_chemical_symbols()) == {"Cu"},
          f"frame {k}: expected pure Cu")
    check(abs(np.array(frame.cell) - ep_cell).max() <= 1e-6,
          f"frame {k} cell differs from the endpoint cell")

end_tol = refs["endpoint_pos_tol_A"]
d0 = abs(band[0].positions - ep_i.positions).max()
d6 = abs(band[-1].positions - ep_f.positions).max()
check(d0 <= end_tol,
      f"band frame 0 deviates from initial.xyz by {d0:.4f} Å (tol {end_tol})")
check(d6 <= end_tol,
      f"band frame {n_expected-1} deviates from final.xyz by {d6:.4f} Å (tol {end_tol})")

# The adatom is the atom that moves most between the two endpoints
ad_idx = int(np.argmax(np.linalg.norm(ep_f.positions - ep_i.positions, axis=1)))
mid = n_expected // 2
ad_move = float(np.linalg.norm(band[mid].positions[ad_idx] - band[0].positions[ad_idx]))
check(ad_move >= refs["min_adatom_displacement_A"],
      f"adatom displacement at mid-band {ad_move:.3f} Å < "
      f"{refs['min_adatom_displacement_A']} — interior frames do not move the "
      f"adatom (copied endpoints?)")

# ── Layer 3: L4 REAL RECOMPUTE — EMT energy of every frame ───────────────────
from ase.calculators.emt import EMT

energies = []
for k, frame in enumerate(band):
    fr = frame.copy()
    fr.calc = EMT()
    energies.append(float(fr.get_potential_energy()))

check(abs(energies[-1] - energies[0]) <= refs["endpoint_degeneracy_tol_eV"],
      f"endpoint energies differ by {abs(energies[-1]-energies[0]):.4f} eV — "
      f"the band does not connect the two degenerate hollow sites")

imax = int(np.argmax(energies))
check(0 < imax < n_expected - 1,
      f"highest-energy frame is {imax} (endpoint) — not a converged band interior")

barrier_re = energies[imax] - energies[0]
b_tol = refs["crossverify_barrier_tol_eV"]
check(abs(barrier_re - values["barrier"]) <= b_tol,
      f"reported barrier {values['barrier']:.6f} eV != barrier recomputed from "
      f"the band geometries {barrier_re:.6f} eV (tol {b_tol})")

# The climbing image must be a converged saddle: full force on it vanishes.
saddle = band[imax].copy()
saddle.calc = EMT()
fmax_saddle = float(np.max(np.linalg.norm(saddle.get_forces(), axis=1)))
check(fmax_saddle < refs["saddle_fmax_threshold"],
      f"recomputed force on the highest-energy frame {fmax_saddle:.4f} eV/Å "
      f">= {refs['saddle_fmax_threshold']} — the band was never optimized to "
      f"convergence (raw interpolation?)")
check(abs(fmax_saddle - values["saddle_fmax"]) <= refs["saddle_fmax_tol"],
      f"reported saddle_fmax {values['saddle_fmax']:.4f} != recomputed "
      f"{fmax_saddle:.4f} (tol {refs['saddle_fmax_tol']})")

# ── Layer 4: Reference anchors ────────────────────────────────────────────────
check(abs(barrier_re - refs["barrier_eV_ref"]) <= refs["barrier_eV_tol"],
      f"barrier {barrier_re:.6f} eV differs from calibrated ref "
      f"{refs['barrier_eV_ref']:.6f} by > {refs['barrier_eV_tol']} eV")

print("PASS: ase-neb-adatom")

#!/usr/bin/env python3
"""
Verifier for ase-vibrations:
  1. File existence + results.json schema (values/units); vib cache present
  2. Geometry integrity: 4 Cu atoms; recomputed EMT forces prove a true
     minimum (fmax < 0.01 eV/Å) — kills "vibrations of a non-stationary
     geometry reported honestly".
  3. CACHE CONSISTENCY: reload the agent's vib/ cache and compare its
     frequencies against results.json — kills "genuine cache, fabricated
     numbers".
  4. L4 REAL RECOMPUTE: rerun the full finite-displacement analysis from
     the agent's optimized.xyz with the same calculator and compare all
     six vibrational frequencies (reported ≡ cache ≡ rerun).
  5. Reference anchors vs calibrated frequencies.
Any anomaly is a hard fail.
"""
import json
import sys
import os
import tempfile

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

FREQ_KEYS = [f"freq_{i}" for i in range(1, 7)]


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def top6(freqs):
    """Six vibrational frequencies (ascending) from a 3N frequency array."""
    return sorted(float(np.real(f)) for f in freqs[-6:])


def n_imag(freqs):
    return int(sum(1 for f in freqs if abs(np.imag(f)) > 10.0))


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("optimized.xyz", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")
check(os.path.isdir(os.path.join(WORKSPACE, "vib")),
      "Missing: vib/ cache directory (Vibrations must run with name='vib')")
cache_files = [f for f in os.listdir(os.path.join(WORKSPACE, "vib"))
               if f.startswith("cache.") and f.endswith(".json")]
check(len(cache_files) >= 24,
      f"vib/ contains {len(cache_files)} cache files (expected >= 24 = 2×3N "
      f"displacements for N=4) — the displacement set is incomplete")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_modes", "n_imaginary", *FREQ_KEYS):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

check(values["n_modes"] == 12, f"n_modes must be 12 (3N, N=4), got {values['n_modes']}")

# ── Layer 2: Geometry integrity — true EMT minimum ────────────────────────────
from ase.io import read
from ase.calculators.emt import EMT

atoms = read(os.path.join(WORKSPACE, "optimized.xyz"))
check(len(atoms) == 4, f"optimized.xyz has {len(atoms)} atoms (expected 4: Cu4)")
check(set(atoms.get_chemical_symbols()) == {"Cu"}, "expected pure Cu cluster")

re_min = atoms.copy()
re_min.calc = EMT()
fmax = float(np.max(np.linalg.norm(re_min.get_forces(), axis=1)))
check(fmax < refs["fmax_threshold_eV_per_A"],
      f"recomputed fmax on optimized.xyz {fmax:.4f} eV/Å >= "
      f"{refs['fmax_threshold_eV_per_A']} — not a converged EMT minimum, so "
      f"any 'vibrational analysis' of it is meaningless")

reported = [float(values[k]) for k in FREQ_KEYS]
check(reported == sorted(reported), "freq_1..freq_6 must be sorted ascending")
check(values["n_imaginary"] == 0,
      f"a true minimum has no imaginary modes; n_imaginary={values['n_imaginary']}")

# ── Layer 3: CACHE CONSISTENCY — reported ≡ agent's vib/ cache ───────────────
from ase.vibrations import Vibrations

vib_cache = Vibrations(atoms, name=os.path.join(WORKSPACE, "vib"))
cache_freqs = vib_cache.get_frequencies()
cache_top6 = top6(cache_freqs)
ctol = refs["cache_consistency_tol_cm1"]
for i, (rep, cac) in enumerate(zip(reported, cache_top6), start=1):
    check(abs(rep - cac) <= ctol,
          f"freq_{i}: reported {rep:.3f} != vib/ cache {cac:.3f} cm^-1 "
          f"(tol {ctol}) — results.json does not match the submitted cache")
check(n_imag(cache_freqs) == 0,
      "the vib/ cache itself contains imaginary vibrational modes — the "
      "cached displacements do not belong to the optimized minimum")

# ── Layer 4: L4 REAL RECOMPUTE — rerun the whole analysis from optimized.xyz ──
tmpdir = tempfile.mkdtemp(prefix="vibrecheck_")
try:
    re_atoms = atoms.copy()
    re_atoms.calc = EMT()
    vib_re = Vibrations(re_atoms, name=os.path.join(tmpdir, "vibre"))
    vib_re.run()
    re_freqs = vib_re.get_frequencies()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

re_top6 = top6(re_freqs)
rtol = refs["crossverify_freq_tol_cm1"]
for i, (rep, re_) in enumerate(zip(reported, re_top6), start=1):
    check(abs(rep - re_) <= rtol,
          f"freq_{i}: reported {rep:.3f} != verifier rerun {re_:.3f} cm^-1 "
          f"(tol {rtol})")
check(n_imag(re_freqs) == 0,
      "verifier rerun found imaginary vibrational modes — optimized.xyz is "
      "not a true minimum under finite displacements")

# ── Layer 5: Reference anchors ────────────────────────────────────────────────
ref_freqs = refs["freqs_cm1_ref"]
ftol = refs["freqs_cm1_tol"]
for i, (re_, ref_) in enumerate(zip(re_top6, ref_freqs), start=1):
    check(abs(re_ - ref_) <= ftol,
          f"freq_{i}: rerun {re_:.3f} cm^-1 differs from calibrated ref "
          f"{ref_:.3f} by > {ftol}")

print("PASS: ase-vibrations")

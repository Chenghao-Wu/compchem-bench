# Authoring assets

`build_starting_geometry.py` deterministically builds the idealized all-anti
n-hexane starting geometry (stdlib python only: C–C 1.54 Å, C–H 1.09 Å,
tetrahedral angles, planar zigzag, staggered methyls with one anti C–H bond).
`relax_and_emit_asset.py` relaxes that geometry with the in-image `pw.x`
(same PBE / ecutwfc=50 Ry / ecutrho=400 Ry / 30-bohr cell settings as the
scan) and writes the released asset `environment/assets/hexane_anti.xyz`,
recentred so the C3–C4 bond midpoint sits exactly at the cell centre (the
relax takes tens of BFGS steps from the idealized start; optionally seed it
from any partially relaxed xyz via the script's second argument to shorten
the run — the converged endpoint is the same). Run from the task root,
inside the task image:

```
python3 authoring/build_starting_geometry.py
python3 authoring/relax_and_emit_asset.py .
```

The pseudopotentials are unmodified upstream files: C from the benchmark's
shared inventory (PSlibrary 1.0.0 kjpaw PAW, also used by `qe-relax-co`) and
H from the Quantum ESPRESSO pseudopotential server (PSlibrary 1.0.0 rrkjus
USPP). SHA-256 of every released file is pinned in `provenance.json` and in
`tests/refs.json` (`asset_hashes`); the verifier re-hashes before any use.

## Protocol rationale and calibration

QE's `pw.x` has no torsion constraint, so the task pins a **rigid scan**:
geometries are exact rotations of the relaxed anti reference about the
C3–C4 axis (moving fragment C4/C5/C6 + their seven H atoms), one SCF single
point per angle, all other internal coordinates frozen. That makes the
profile a pure function of the protocol — reproducible to ~1e-8 Ry across
runs on the pinned image — and lets the verifier (a) check every logged
geometry against the nominal dihedral and the asset's 19-bond fingerprint,
and (b) re-run three angles from the agent's own logged coordinates.

Reference values in `tests/refs.json` are calibrated from oracle runs of
`solution/solve.sh` on x86_64 against the pinned image (digest recorded in
`refs.json`). Repeat oracle runs on one host reproduce every energy exactly
at the 1e-8 Ry print resolution; the per-angle gate is 1e-5 Ry (the
benchmark-wide QE convention). The three recomputed angles must agree with
the agent logs and `results.json` to 1e-6 Ry. Because the profile is fully
determined by the pinned protocol and asset, a forger cannot guess seven
absolute DFT energies to tolerance, and the recompute defeats fabricated
logs with self-consistent guessed numbers. `provenance.json` records the
source hashes, the image digest, and the exact tolerance rules.

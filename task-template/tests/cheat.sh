#!/usr/bin/env bash
# Informed cheat: a plausible, self-consistent, domain-aware forgery of every
# required file — NOT echo/touch stubs. Models a forger who knows the software
# and the task but does NOT run the real calculation.
#
# CI requires this to FAIL (the verifier's L4 recompute must catch it). Write
# the forgery so it is self-consistent (e.g. a results.json whose reported
# number actually equals what a recompute of the *fake* state would give),
# so that the ONLY thing that catches it is the real recompute against the
# calibrated reference — that is what proves L4 is doing its job.
set -euo pipefail
mkdir -p /workspace
cd /workspace

# TODO(author): forge the outputs. Example (ASE): build a plausible-but-unoptimized
# geometry, attach SinglePointCalculator results (fabricated energies/forces),
# write a trajectory + a results.json whose energy is the TRUE pinned-calculator
# energy of the fake geometry — so an energy-only check would pass, but the
# force recompute (or reference tolerance) fails. See
# tasks/ase-geoopt-h2o/tests/cheat.sh for a worked example.

echo "TODO(author): implement informed cheat.sh"
exit 0

#!/usr/bin/env bash
# Regenerates the sample artifacts for qe-output-parse by REALLY running
# pw.x inside this task's image (QE is open source — no fabricated assets,
# c.f. the vasp-output-parse lesson). The committed files under
# environment/assets/sample_run/ were produced by exactly this script.
#
# Usage (from the repo root, image already built):
#   cid=$(docker create compchem-bench/qe-output-parse:ci \
#         bash /work/generate_assets.sh)
#   docker cp tasks/qe-output-parse/environment "$cid:/work"
#   docker start -a "$cid"
#   docker cp "$cid:/work/assets/sample_run" \
#     tasks/qe-output-parse/environment/assets/
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p pseudo
# The Si pseudopotential ships inside the image at
# /opt/qe-pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF (baked from shared/potentials/qe/).
cp /opt/qe-pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF pseudo/

rm -rf outdir assets/sample_run
pw.x -in assets_src/si_sample.in > si_sample.out

mkdir -p assets/sample_run
mv si_sample.out assets/sample_run/
mv outdir/pwscf.xml assets/sample_run/
rm -rf outdir pseudo

echo "Generated assets/sample_run/si_sample.out + assets/sample_run/pwscf.xml"

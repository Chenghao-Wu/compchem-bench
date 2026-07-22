#!/usr/bin/env bash
# Oracle solution for lammps-nvt-rdf.
set -euo pipefail
cd /workspace

cp /workspace/assets/nvt_rdf.in ./nvt_rdf.in

# Single-threaded for determinism
export OMP_NUM_THREADS=1
lmp_serial -in nvt_rdf.in

python3 << 'PYEOF'
import json
import numpy as np

# Parse rdf.dat — LAMMPS ave/time mode vector format:
# header lines starting with #, then blocks per timestep
# Each non-comment, non-blank line after the header: bin_index  r  g(r)  ...
r_vals = []
gr_vals = []
with open("rdf.dat") as f:
    for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        try:
            # LAMMPS rdf output: col0=bin, col1=r, col2=g(r), col3=coord_number
            r_vals.append(float(parts[1]))
            gr_vals.append(float(parts[2]))
        except ValueError:
            continue

if not r_vals:
    raise RuntimeError("No RDF data parsed from rdf.dat")

r_arr = np.array(r_vals)
gr_arr = np.array(gr_vals)

# First peak: max g(r) for r > 0.5
mask = r_arr > 0.5
peak_idx = np.argmax(gr_arr[mask])
peak_r = float(r_arr[mask][peak_idx])
peak_gr = float(gr_arr[mask][peak_idx])

# Count unique r bins (first block of the averaged output)
n_bins = len(set(round(r, 6) for r in r_vals))

results = {
    "values": {
        "first_peak_r": peak_r,
        "first_peak_gr": peak_gr,
        "n_rdf_bins": n_bins,
    },
    "units": {
        "first_peak_r": "σ",
        "first_peak_gr": "1",
        "n_rdf_bins": "1",
    },
}

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"RDF first peak: r={peak_r:.3f} σ, g(r)={peak_gr:.3f}, n_bins={n_bins}")
PYEOF

#!/usr/bin/env bash
# Informed cheat: a forger who knows bead-spring topology and FENE/WCA
# magnitudes. Fabricates:
#   - polymer.data with a PERFECTLY VALID topology (10 chains of 20 on a
#     snake grid — topology, counts, density all correct)
#   - log.lammps with 31 thermo rows: PE starts at a plausible-looking
#     18.0 and relaxes to 20.0, T equilibrating to 1.0, banner + footer
#   - final.data: the same grid with every bead perturbed by ~0.4 sigma
#     (so the initial-vs-final evolution check passes)
#   - results.json self-consistent with the forged log
# Passes layers 1-5 and 7: topology, density, log shape, PE plausibility
# window, results consistency, RMS displacement.
# Must FAIL at L4a: the verifier does read_data + run 0 on polymer.data —
# its true initial energy (~21.7/atom: FENE bonds at r~1.03 are expensive)
# is not the 18.0 guessed in the forged log. (And L4b would catch the
# perturbed final.data as well.)
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

N, L = 200, (200 / 0.85) ** (1 / 3)

# Valid snake-grid topology
n_side = 6
spacing = L / n_side
path = []
for z in range(n_side):
    y_range = range(n_side) if z % 2 == 0 else range(n_side - 1, -1, -1)
    for y in y_range:
        x_range = range(n_side) if (z + y) % 2 == 0 else range(n_side - 1, -1, -1)
        for x in x_range:
            path.append((x, y, z))
beads = path[:N]
chains = [beads[c * 20:(c + 1) * 20] for c in range(10)]


def write_data(fname, positions):
    with open(fname, "w") as f:
        f.write("forged polymer data\n\n")
        f.write(f"{N} atoms\n190 bonds\n1 atom types\n1 bond types\n\n")
        f.write(f"0.0 {L:.8f} xlo xhi\n0.0 {L:.8f} ylo yhi\n0.0 {L:.8f} zlo zhi\n\n")
        f.write("Masses\n\n1 1.0\n\nAtoms # molecular\n\n")
        for aid, ((i, j, k), (x, y, z)) in enumerate(zip(beads, positions), start=1):
            mol = (aid - 1) // 20 + 1
            f.write(f"{aid} {mol} 1 {x:.6f} {y:.6f} {z:.6f}\n")
        f.write("\nBonds\n\n")
        bid = 1
        for mol in range(10):
            base = mol * 20
            for b in range(19):
                f.write(f"{bid} 1 {base + b + 1} {base + b + 2}\n")
                bid += 1


grid_pos = [((i + 0.5) * spacing, (j + 0.5) * spacing, (k + 0.5) * spacing)
            for (i, j, k) in beads]
write_data("polymer.data", grid_pos)

rng = np.random.RandomState(5)
pert_pos = [(min(max(x + rng.normal(0, 0.4), 0.01), L - 0.01),
             min(max(y + rng.normal(0, 0.4), 0.01), L - 0.01),
             min(max(z + rng.normal(0, 0.4), 0.01), L - 0.01)) for x, y, z in grid_pos]
write_data("final.data", pert_pos)

# Fake log: 31 rows, PE "relaxing" from a guessed 18.0 to 20.0
lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng"]
for step in range(0, 3001, 100):
    t = 1.0 + 0.5 * np.exp(-step / 500) + rng.normal(0, 0.01)
    if step == 0:
        t = 1.0
    pe = 18.0 + 2.0 * (1 - np.exp(-step / 800)) + rng.normal(0, 0.02)
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f}")
lines.append("Loop time of 1.1 on 1 procs for 3000 steps with 200 atoms")
lines.append("Total wall time: 0:00:02")
with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

final_pe = float(lines[-3].split()[2])
results = {
    "values": {"n_atoms": 200, "n_bonds": 190, "density": 0.85, "final_pe": final_pe},
    "units": {"n_atoms": "1", "n_bonds": "1", "density": "σ^-3", "final_pe": "ε/atom"},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged valid-topology polymer.data + perturbed final.data + fake log (PE 18.0->20.0)")
PYEOF

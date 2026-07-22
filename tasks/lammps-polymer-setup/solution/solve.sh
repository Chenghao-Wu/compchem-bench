#!/usr/bin/env bash
# Oracle solution for lammps-polymer-setup.
set -euo pipefail
cd /workspace

# ── Step 1: build polymer.data (self-avoiding random walks on a lattice) ──
python3 << 'PYEOF'
N_CHAINS, N_BEADS = 10, 20
RHO = 0.85
N = N_CHAINS * N_BEADS
L = (N / RHO) ** (1.0 / 3.0)

# 6x6x6 grid (216 sites >= 200 beads), spacing L/6 ~ 1.03 sigma — every
# nearest-neighbour distance is comfortably outside the WCA core.
# Chains follow a 3D boustrophedon (snake) path so consecutive beads are
# always grid neighbours.
n_side = 6
spacing = L / n_side
path = []
for z in range(n_side):
    y_range = range(n_side) if z % 2 == 0 else range(n_side - 1, -1, -1)
    for y in y_range:
        if (z + y) % 2 == 0:
            x_range = range(n_side)
        else:
            x_range = range(n_side - 1, -1, -1)
        for x in x_range:
            path.append((x, y, z))
assert len(path) == 216

beads = path[:N]
chains = [beads[c * N_BEADS:(c + 1) * N_BEADS] for c in range(N_CHAINS)]

with open("polymer.data", "w") as f:
    f.write("LAMMPS data: Kremer-Grest bead-spring melt, 10x20, rho=0.85\n\n")
    f.write(f"{N} atoms\n")
    f.write(f"{N_CHAINS * (N_BEADS - 1)} bonds\n")
    f.write("1 atom types\n")
    f.write("1 bond types\n\n")
    f.write(f"0.0 {L:.8f} xlo xhi\n0.0 {L:.8f} ylo yhi\n0.0 {L:.8f} zlo zhi\n\n")
    f.write("Masses\n\n1 1.0\n\n")
    f.write("Atoms # molecular\n\n")
    aid = 1
    for mol, walk in enumerate(chains, start=1):
        for (i, j, k) in walk:
            f.write(f"{aid} {mol} 1 {(i+0.5)*spacing:.6f} {(j+0.5)*spacing:.6f} {(k+0.5)*spacing:.6f}\n")
            aid += 1
    f.write("\nBonds\n\n")
    bid = 1
    for mol in range(N_CHAINS):
        base = mol * N_BEADS
        for b in range(N_BEADS - 1):
            f.write(f"{bid} 1 {base + b + 1} {base + b + 2}\n")
            bid += 1
print(f"polymer.data: {N} atoms, {N_CHAINS*(N_BEADS-1)} bonds, L={L:.6f}")
PYEOF

# ── Step 2: NVT equilibration ─────────────────────────────────────────────
cat > equil.in << 'EOF'
units           lj
atom_style      molecular
boundary        p p p

bond_style      fene
special_bonds   fene
pair_style      lj/cut 1.12246204830937

read_data       polymer.data

pair_coeff      * * 1.0 1.0 1.12246204830937
pair_modify     shift yes
bond_coeff      1 30.0 1.5 1.0 1.0

neighbor        0.4 bin
neigh_modify    every 1 delay 0 check yes

velocity        all create 1.0 8675309

timestep        0.006

thermo          100
thermo_style    custom step temp pe

fix             1 all nvt temp 1.0 1.0 1.0
run             3000

write_data      final.data
EOF

export OMP_NUM_THREADS=1
lmp_serial -in equil.in

# ── Step 3: results.json ──────────────────────────────────────────────────
python3 << 'PYEOF'
import json
import re

with open("log.lammps") as f:
    log = f.read()

thermo = []
in_run = False
for line in log.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[-\d.eE+]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

if len(thermo) != 31:
    raise RuntimeError(f"Expected 31 thermo rows, got {len(thermo)}")

final_pe = float(thermo[-1].split()[2])
results = {
    "values": {
        "n_atoms": 200,
        "n_bonds": 190,
        "density": 0.85,
        "final_pe": final_pe,
    },
    "units": {
        "n_atoms": "1",
        "n_bonds": "1",
        "density": "σ^-3",
        "final_pe": "ε/atom",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"final_pe = {final_pe:.6f} ε/atom")
PYEOF

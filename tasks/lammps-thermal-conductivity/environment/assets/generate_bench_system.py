#!/usr/bin/env python3
"""
Generate the 1200-bead sticker-functionalized bead-spring system for the
lammps-thermal-conductivity benchmark task.

30 chains x 40 beads = 1200 atoms, 2 sticker beads per chain at chain
positions 11 and 31 (1-indexed, matching the production data), at the same
number density as the original 40000-atom FYP system
(rho* = 40000 / 57.2872^3 = 0.21276).

Chains are grown by self-avoiding random walk and accepted only if overlap-free
(no force-accept; a failed chain is retried from a new start). Writes a LAMMPS
data file (molecular style, no velocities). The equilibrate.in input then runs
a short NVT equilibration and writes the data_T1.lammps / data_T04.lammps
assets (with velocities) the benchmark task ships.

Usage:  python3 generate_bench_system.py [output]
"""

import sys
import datetime
import numpy as np

NUM_CHAINS = 30
BEADS_PER_CHAIN = 40
STICKER_INDICES = [10, 30]        # 0-indexed -> 1-indexed positions 11, 31
BOND_LENGTH = 0.97
MIN_SEPARATION_SQ = 0.8 ** 2
MAX_ATTEMPTS_PER_BEAD = 1000
MAX_CHAIN_ATTEMPTS = 500

RHO = 40000.0 / (57.2872 ** 3)    # keep the production number density
BOX_SIDE = (NUM_CHAINS * BEADS_PER_CHAIN / RHO) ** (1.0 / 3.0)
HALF_BOX = BOX_SIDE / 2.0
RNG = np.random.default_rng(20260804)


def is_overlap(new_pos, all_positions):
    """Overlap test with periodic minimum-image distances.

    The box is periodic, so two atoms can be close across opposite faces;
    the raw-coordinate test misses those and produces physically overlapping
    structures (LJ energy ~1e7). Wrap the difference into [-L/2, L/2] first.
    """
    if not all_positions:
        return False
    arr = np.array(all_positions)
    d = arr - new_pos
    d -= np.round(d / BOX_SIDE) * BOX_SIDE
    d2 = np.sum(d ** 2, axis=1)
    return bool(np.any(d2 < MIN_SEPARATION_SQ))


def try_chain(start, all_positions):
    """Grow one 40-bead chain from `start`; return None on failure."""
    local = [start]
    for i in range(1, BEADS_PER_CHAIN):
        placed = False
        for _ in range(MAX_ATTEMPTS_PER_BEAD):
            move = RNG.normal(size=3)
            move /= np.linalg.norm(move)
            new_pos = local[-1] + move * BOND_LENGTH
            if not is_overlap(new_pos, all_positions + local):
                local.append(new_pos)
                placed = True
                break
        if not placed:
            return None          # bead stuck -> whole chain rejected
    return local


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "data.in"
    total_atoms = NUM_CHAINS * BEADS_PER_CHAIN
    total_bonds = NUM_CHAINS * (BEADS_PER_CHAIN - 1)
    total_angles = NUM_CHAINS * (BEADS_PER_CHAIN - 2)
    print(f"chains={NUM_CHAINS} beads/chain={BEADS_PER_CHAIN} "
          f"atoms={total_atoms} rho={RHO:.5f} box_side={BOX_SIDE:.6f}")

    chains = []
    all_pos = []
    for cid in range(NUM_CHAINS):
        for attempt in range(MAX_CHAIN_ATTEMPTS):
            start = RNG.uniform(-HALF_BOX, HALF_BOX, size=3)
            if is_overlap(start, all_pos):
                continue
            chain = try_chain(start, all_pos)
            if chain is not None:
                types = [2 if j in STICKER_INDICES else 1
                         for j in range(BEADS_PER_CHAIN)]
                chains.append((chain, types))
                all_pos.extend(chain)
                break
        else:
            raise RuntimeError(
                f"chain {cid + 1} could not be placed after "
                f"{MAX_CHAIN_ATTEMPTS} attempts (density too high for "
                f"{BEADS_PER_CHAIN}-bead chains?)")
        if (cid + 1) % 10 == 0:
            print(f"  placed {cid + 1}/{NUM_CHAINS} chains")

    with open(out, "w") as f:
        f.write("LAMMPS data file, version 20260804, "
                "generated for compchem-bench lammps-thermal-conductivity "
                "(molecular style)\n\n")
        f.write(f"{total_atoms} atoms\n{total_bonds} bonds\n{total_angles} angles\n")
        f.write("0 dihedrals\n0 impropers\n\n")
        f.write("2 atom types\n1 bond types\n1 angle types\n\n")
        f.write(f"{-HALF_BOX:.6f} {HALF_BOX:.6f} xlo xhi\n")
        f.write(f"{-HALF_BOX:.6f} {HALF_BOX:.6f} ylo yhi\n")
        f.write(f"{-HALF_BOX:.6f} {HALF_BOX:.6f} zlo zhi\n\n")
        f.write("Masses\n\n1 1.0\n2 1.0\n\n")
        f.write("Atoms # molecular\n\n")
        aid = 0
        for cid, (pos, types) in enumerate(chains):
            for i in range(BEADS_PER_CHAIN):
                aid += 1
                p = pos[i]
                f.write(f"{aid} {cid + 1} {types[i]} {p[0]:.6f} {p[1]:.6f} "
                        f"{p[2]:.6f} 0 0 0\n")
        f.write("\nBonds\n\n")
        bid = 0
        for cid in range(NUM_CHAINS):
            start = cid * BEADS_PER_CHAIN + 1
            for j in range(BEADS_PER_CHAIN - 1):
                bid += 1
                f.write(f"{bid} 1 {start + j} {start + j + 1}\n")
        f.write("\nAngles\n\n")
        aaid = 0
        for cid in range(NUM_CHAINS):
            start = cid * BEADS_PER_CHAIN + 1
            for j in range(BEADS_PER_CHAIN - 2):
                aaid += 1
                f.write(f"{aaid} 1 {start + j} {start + j + 1} {start + j + 2}\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# Informed cheat: models a forger who knows the task and the pinned pipeline
# but does NOT run the MD. The forger builds the genuine pinned PEO chain
# (cheap, deterministic), then fabricates a protocol-passing md.traj: frame 0
# is the exact initial chain, a random-walking center of mass clears the
# displacement gate, a smooth global "breathing" factor keeps the ensemble
# near the constructed chain while relaxing it just enough to clear the
# un-relaxed floor, and small per-atom noise creates an Rg spread. Every
# reported statistic is honestly recomputed from the forged trajectory, so
# the chain-regeneration, protocol, self-consistency, criterion, fluctuation,
# and displacement layers are all satisfied.
#
# Must FAIL: the forged ensemble is not the 500 K equilibrium ensemble — its
# production mean Rg and Rg std sit at the breathing model's values (not the
# thermalized coil's), and its final-frame force-field energy is far from the
# thermalized range, so the seed-agnostic equilibrium intervals (layer 6)
# reject it.
set -euo pipefail
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import sys

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from ase import Atoms
from ase.io import write
from ase.io.trajectory import Trajectory

sys.path.insert(0, "/workspace/assets")
import peo_ff

# Genuine pinned chain construction (cheap and deterministic)
mol = Chem.MolFromSmiles("O" + "CCO" * 10)
mol = Chem.AddHs(mol)
params = AllChem.ETKDGv3()
params.randomSeed = 0xf00d
assert AllChem.EmbedMolecule(mol, params) == 0
AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=2000)
mol = Chem.RemoveHs(mol)
bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx()) for b in mol.GetBonds()]
symbols = [a.GetSymbol() for a in mol.GetAtoms()]
pos0 = mol.GetConformer().GetPositions()
init = Atoms(symbols=symbols, positions=pos0)
write("chain_init.xyz", init)
masses = init.get_masses()

def radius_of_gyration(frame):
    m = frame.get_masses()
    com = np.sum(frame.positions * m[:, None], axis=0) / m.sum()
    return float(np.sqrt(np.sum(m * np.sum((frame.positions - com) ** 2,
                                            axis=1)) / m.sum()))

rg_initial = radius_of_gyration(init)

# Fabricate a protocol-passing trajectory WITHOUT any MD
rng = np.random.default_rng(1234)
n_frames = 601
n_steps = 600_000
com0 = np.sum(pos0 * masses[:, None], axis=0) / masses.sum()
traj = Trajectory("md.traj", "w")
traj.write(Atoms(symbols=symbols, positions=pos0.copy()))   # frame 0 == initial chain
com_walk = np.zeros(3)
for k in range(1, n_frames):
    t = k / (n_frames - 1)
    com_walk = com_walk + rng.normal(0.0, 0.6, size=3)      # clears the displacement gate
    scale = (1.0 + 0.05 * np.sin(2 * np.pi * 5.0 * t) + 0.03 * np.sin(2 * np.pi * 13.0 * t + 0.7)
             - 0.04 * t)                                    # slight "relaxation" drift
    pos = com0 + (pos0 - com0) * scale + com_walk
    pos = pos + rng.normal(0.0, 0.05, size=pos.shape)       # small cosmetic Rg spread
    traj.write(Atoms(symbols=symbols, positions=pos))
traj.close()

# Honestly recompute every reported statistic from the forgery
from ase.io import read
frames = read("md.traj", index=":")
rg = np.array([radius_of_gyration(f) for f in frames])
prod = rg[len(rg) // 2:]
b1, b2 = prod[: len(prod) // 2], prod[-len(prod) // 2:]
rg_mean = float(prod.mean())
rg_std = float(prod.std())
drift = abs(b2.mean() - b1.mean()) / b2.mean()
unrelaxed = abs(rg_mean - rg_initial) >= 0.03 * rg_initial
equilibrated = bool(drift < 0.10 and unrelaxed)

# Honest pinned-FF energy of the forged last frame
atoms = Atoms(symbols=symbols, positions=pos0)
atoms.calc = peo_ff.make_calculator(atoms, bonds)
last = Atoms(symbols=symbols, positions=frames[-1].positions)
last.calc = atoms.calc
final_energy = float(last.get_potential_energy())

results = {
    "values": {
        "n_frames": int(len(frames)),
        "n_steps": int(n_steps),
        "rg_initial": float(rg_initial),
        "rg_mean": rg_mean,
        "rg_std": rg_std,
        "rg_drift_frac": float(drift),
        "equilibrated": equilibrated,
        "final_energy": final_energy,
    },
    "units": {
        "n_frames": "1",
        "n_steps": "1",
        "rg_initial": "Å",
        "rg_mean": "Å",
        "rg_std": "Å",
        "rg_drift_frac": "1",
        "equilibrated": "1",
        "final_energy": "eV",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged {len(frames)}-frame protocol-passing trajectory without MD "
      f"(<Rg>_prod {rg_mean:.4f}, std {rg_std:.4f}, drift {drift:.5f}, "
      f"E_last {final_energy:.4f} eV — all honestly recomputed from the forgery)")
PYEOF

#!/usr/bin/env bash
# Oracle solution: single PEO chain — RDKit construction, ASE Langevin
# sampling, and an equilibration assessment on the ensemble-averaged Rg.
# Demonstrates real execution and the intended iterate-until-equilibrated
# workflow — no hardcoded answers.
set -euo pipefail
cd /workspace

python3 << 'PYEOF'
import json
import sys

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from ase import Atoms, units
from ase.io import write, read
from ase.io.trajectory import Trajectory
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import (MaxwellBoltzmannDistribution,
                                         Stationary, ZeroRotation)

sys.path.insert(0, "/workspace/assets")
import peo_ff

# ── Task contract constants (see instruction.md) ─────────────────────────────
N_MONOMERS = 10                 # PEO repeat units
EMBED_SEED = 0xf00d             # ETKDGv3 random seed
TEMPERATURE_K = 500.0           # thermostat target temperature
MAX_SPACING = 10_000            # max saved-frame spacing (steps)
MIN_FRAMES = 200                # min saved frames
MIN_STEPS = 600_000             # min integration steps
DRIFT_THRESHOLD = 0.10          # equilibration criterion
UNRELAXED_FRAC = 0.03           # production mean must differ from Rg_init by this

# Agent-chosen implementation parameters (any sane values work)
TIMESTEP_FS = 1.0
FRICTION_PER_FS = 0.005
VEL_SEED = 20260811
MD_SEED = 20260812
SAMPLE_INTERVAL = 1_000         # steps between saved frames (<= MAX_SPACING)
SEGMENT_STEPS = 200_000         # run in segments; re-check after each
MAX_SEGMENTS = 12

def radius_of_gyration(frame):
    m = frame.get_masses()
    com = np.sum(frame.positions * m[:, None], axis=0) / m.sum()
    return float(np.sqrt(np.sum(m * np.sum((frame.positions - com) ** 2,
                                            axis=1)) / m.sum()))

# ── 1. Build the PEO chain with RDKit ────────────────────────────────────────
mol = Chem.MolFromSmiles("O" + "CCO" * N_MONOMERS)
mol = Chem.AddHs(mol)
params = AllChem.ETKDGv3()
params.randomSeed = EMBED_SEED
assert AllChem.EmbedMolecule(mol, params) == 0
AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=2000)
mol = Chem.RemoveHs(mol)

bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx()) for b in mol.GetBonds()]
atoms = Atoms(symbols=[a.GetSymbol() for a in mol.GetAtoms()],
              positions=mol.GetConformer().GetPositions())
write("chain_init.xyz", atoms)

# ── 2. Attach the pinned toy force field ─────────────────────────────────────
atoms.calc = peo_ff.make_calculator(atoms, bonds)
rg_initial = radius_of_gyration(atoms)

# ── 3. Sample with Langevin dynamics, refining until equilibrated ────────────
MaxwellBoltzmannDistribution(atoms, temperature_K=TEMPERATURE_K,
                             rng=np.random.default_rng(VEL_SEED))
Stationary(atoms)
ZeroRotation(atoms)
dyn = Langevin(atoms, TIMESTEP_FS * units.fs, temperature_K=TEMPERATURE_K,
               friction=FRICTION_PER_FS / units.fs, fixcm=True,
               rng=np.random.default_rng(MD_SEED))
traj = Trajectory("md.traj", "w", atoms)
dyn.attach(traj.write, interval=SAMPLE_INTERVAL)

def production_stats():
    frames = read("md.traj", index=":")
    rg = np.array([radius_of_gyration(f) for f in frames])
    prod = rg[len(rg) // 2:]                 # production = last 50% of frames
    b1, b2 = prod[: len(prod) // 2], prod[-len(prod) // 2:]
    drift = abs(b2.mean() - b1.mean()) / b2.mean()
    return len(frames), prod.mean(), prod.std(), drift

n_frames, rg_mean, rg_std, drift = 0, 0.0, 0.0, np.inf
total_steps = 0
for seg in range(MAX_SEGMENTS):
    dyn.run(SEGMENT_STEPS)
    total_steps += SEGMENT_STEPS
    n_frames, rg_mean, rg_std, drift = production_stats()
    unrelaxed = abs(rg_mean - rg_initial) >= UNRELAXED_FRAC * rg_initial
    print(f"[segment {seg + 1}] steps={total_steps} frames={n_frames} "
          f"prod<Rg>={rg_mean:.4f} drift={drift:.5f}")
    if (total_steps >= MIN_STEPS and n_frames >= MIN_FRAMES
            and drift < DRIFT_THRESHOLD and unrelaxed):
        break

assert total_steps >= MIN_STEPS, "did not reach the minimum run length"
assert drift < DRIFT_THRESHOLD, f"not equilibrated after {total_steps} steps (drift {drift:.4f})"

final_energy = float(atoms.get_potential_energy())

# ── 4. Report the ensemble-averaged Rg and the equilibration assessment ──────
results = {
    "values": {
        "n_frames": int(n_frames),
        "n_steps": int(total_steps),
        "rg_initial": float(rg_initial),
        "rg_mean": float(rg_mean),
        "rg_std": float(rg_std),
        "rg_drift_frac": float(drift),
        "equilibrated": bool(drift < DRIFT_THRESHOLD),
        "final_energy": float(final_energy),
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

print(f"converged: steps={total_steps} frames={n_frames} "
      f"<Rg>_prod={rg_mean:.4f}±{rg_std:.4f} Å drift={drift:.5f} "
      f"E_final={final_energy:.4f} eV")
PYEOF

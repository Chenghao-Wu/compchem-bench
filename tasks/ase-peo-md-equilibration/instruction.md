# Task: PEO Chain Sampling and Rg-Based Equilibration Assessment (RDKit + ASE)

## Background

Single-chain polymer simulations begin from a constructed — and therefore
non-equilibrium — geometry. Only after the chain has relaxed do its
conformational ensemble averages become meaningful, so the equilibration of
the simulation must be evaluated before any production quantity is trusted.
The diagnostic used here is the **ensemble-averaged radius of gyration**:
the mean Rg over an early portion of the sampled production ensemble must
agree with the mean over a later portion.

You will build one polyethylene oxide (PEO) chain with RDKit, sample its
conformations with Langevin molecular dynamics in ASE, and evaluate the
equilibration of the simulation from the ensemble-averaged Rg. You decide
the numerical details of the sampler — timestep, friction, seeds, run
length, and how often you save — subject to the sampling protocol and the
equilibration criterion below. A run that does not meet the criterion has
not equilibrated; extend it until it does.

## Your Task

### 1. Construct the chain (RDKit)

Build HO–(CH2–CH2–O)10–H: ten `CCO` repeat units between hydroxyl caps,
parsed from SMILES. Add explicit hydrogens, embed a single 3D conformer with
the ETKDGv3 distance-geometry protocol at random seed `0xf00d` (61453),
relax with the **MMFF94** force field to convergence, then remove all
hydrogens — the pinned force field below is a heavy-atom model. The result
is a 31-atom chain. Convert it to an ASE `Atoms` preserving the RDKit atom
order, with positions from the conformer in Å, and write it to
`chain_init.xyz`.

### 2. Attach the pinned force field

The force field is fixed: `/workspace/assets/peo_ff.py` implements harmonic
bonds and harmonic angles (equilibrium values frozen from the constructed
geometry when the calculator is built) plus a WCA non-bonded repulsion that
excludes 1-2 and 1-3 pairs. Build it with `peo_ff.make_calculator(atoms,
bonds)`, where `bonds` are the bond index pairs taken from the RDKit
molecule. Do not modify the file.

### 3. Sample conformations (ASE Langevin dynamics)

Run NVT Langevin dynamics (`ase.md.langevin.Langevin`) on the chain at a
target temperature of **500 K**, saving conformations to the ASE trajectory
`md.traj`. The sampling protocol is part of the contract:

- the first saved frame is the constructed starting structure;
- then save the evolving state at regular intervals of **at most 10 000
  integration steps** — no trimming, re-weighting, or selective discarding;
- the run integrates **at least 600 000 steps** in total and saves **at
  least 200 frames**;
- the dynamics must actually advance the system: by the last frame the
  chain must have moved far from its starting geometry.

You choose the timestep (keep it stable for this stiff-bond model), the
friction, and the random seeds. Fix them so the run is reproducible.

### 4. Evaluate equilibration from the ensemble-averaged Rg

For every saved frame compute the mass-weighted radius of gyration

Rg² = (1/M) Σᵢ mᵢ |rᵢ − r_com|²,  with r_com the mass-weighted centroid

using standard ASE atomic masses. Take the **production ensemble** to be the
last 50% of the saved frames (discard the first half as equilibration), and
split it into an early and a late half. Report:

- `rg_mean` — ensemble-averaged Rg over the production ensemble;
- `rg_std` — standard deviation of Rg over the production ensemble;
- `rg_drift_frac` — |mean(late half) − mean(early half)| / mean(late half);
- `equilibrated` — `true` if the criterion below is met, otherwise `false`.

**Equilibration criterion.** The simulation is equilibrated only when the
production ensemble satisfies

```
rg_drift_frac < 0.10        (first/second-half ensemble averages agree)
|rg_mean − rg_initial| ≥ 0.03 · rg_initial   (the chain has actually relaxed)
```

where `rg_initial` is the Rg of the constructed chain before the MD run.
A run that fails either condition is not equilibrated — extend the sampling
(or, if the production ensemble is still drifting, run longer) until both
hold. Record the force-field energy of the final structure (`final_energy`).

### 5. Write `results.json`

Write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "n_frames": <int>,
    "n_steps": <int>,
    "rg_initial": <float, Å>,
    "rg_mean": <float, Å>,
    "rg_std": <float, Å>,
    "rg_drift_frac": <float>,
    "equilibrated": <bool>,
    "final_energy": <float, eV>
  },
  "units": {
    "n_frames": "1",
    "n_steps": "1",
    "rg_initial": "Å",
    "rg_mean": "Å",
    "rg_std": "Å",
    "rg_drift_frac": "1",
    "equilibrated": "1",
    "final_energy": "eV"
  }
}
```

`n_frames` is the number of frames in `md.traj`; `n_steps` is the total
number of integration steps.

## Requirements

- The grading is seed-agnostic: any faithful Langevin sampling of the pinned
  chain at 500 K converges to the same equilibrium ensemble. You do not need
  to match any particular trajectory — only to have genuinely sampled the
  equilibrium ensemble and to have honestly assessed its equilibration.
- Do **not** hardcode or fabricate results. The verifier independently:
  (a) regenerates the chain with the pinned RDKit pipeline and requires
  `chain_init.xyz` to match it; (b) recomputes the full Rg series and every
  reported statistic from your trajectory's positions; (c) recomputes the
  force-field energy of your final frame using the integrity-checked
  `peo_ff.py`; (d) confirms the chain genuinely evolved across the run; and
  (e) requires your production ensemble statistics to fall within the
  calibrated equilibrium intervals. Fabricated or cosmetically perturbed
  trajectories, shortened or unrelaxed runs, and modified force fields are
  rejected.
- `md.traj` must be a valid ASE trajectory readable by `ase.io.read`,
  contain frames of 31 atoms each with the chain's element order preserved,
  and its first frame must match `chain_init.xyz`.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/peo_ff.py` (pinned force field — do not modify)
- Output: `chain_init.xyz`, `md.traj`, `results.json` in `/workspace/`

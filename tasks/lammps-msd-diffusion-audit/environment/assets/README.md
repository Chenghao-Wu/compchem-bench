# Liquid Water Simulation — TIP3P, 1 ns at 300 K

Classical MD of liquid water with LAMMPS (22 Jul 2025, update 5), followed by
mean-squared-displacement (MSD) analysis and a self-diffusion coefficient.
Analysis by J. — ready for the group report.

## System

- **Model:** TIP3P water (Jorgensen et al., J. Chem. Phys. 79, 926 (1983))
  - q(O) = −0.834 e, q(H) = +0.417 e
  - O LJ: ε = 0.1521 kcal/mol, σ = 3.1507 Å; H LJ = 0
  - rigid O–H bonds / H–O–H angle via SHAKE
- **Size:** 1000 molecules (3000 atoms), cubic box, ρ ≈ 1.00 g/cm³ initial guess
- **Conditions:** periodic boundaries, 9 Å cutoff, PPPM (1e-4) for electrostatics,
  LJ tail corrections, 2 fs timestep

## Protocol (`in.lammps`)

| Stage        | Ensemble | Duration | Notes                          |
|--------------|----------|----------|--------------------------------|
| minimization | —        | 37 steps | conjugate gradient             |
| equilibration| NVT      | 50 ps    | 300 K, Nosé–Hoover (100 fs)    |
| equilibration| NPT      | 200 ps   | 300 K, 1 atm (iso, 1 ps damp)  |
| production   | NVT      | **1 ns** | 300 K; MSD + trajectory output |

Equilibrated density at end of NPT: 0.992 g/cm³ (T ≈ 300.7 K).
Production potential energy ≈ −9.59 kcal/mol per water.

## MSD and diffusion coefficient

MSD of the oxygen atoms (COM drift removed, reference = production start) was
computed on the fly by LAMMPS (`compute msd ... com yes`) and written every
0.5 ps to `msd.dat` (columns: step, msd_x, msd_y, msd_z, msd_total, in Å²).

Einstein fit over the requested window 50–100 ps (see `analyze_msd.py` and
`diffusion_summary.txt`):

- slope = 3.42 Å²/ps, R² = 0.9992 — the MSD is cleanly diffusive
- **D = 1.71 × 10⁻⁴ cm²/s** (per-axis: x 6.7, y 5.2, z 5.3 × 10⁻⁵ cm²/s)

This agrees well with the well-established diffusivity of liquid water at
ambient conditions, so I am confident in the number.

## Files

| File                  | Contents                                            |
|-----------------------|-----------------------------------------------------|
| `in.lammps`           | complete simulation input script                    |
| `log.lammps`          | run log                                             |
| `msd.dat`             | MSD vs step: step, msd_x, msd_y, msd_z, msd_total (Å²) |
| `analyze_msd.py`      | Einstein fit + plot                                 |
| `msd_analysis.png`    | MSD plot with fit                                   |
| `diffusion_summary.txt` | numerical summary of D                            |

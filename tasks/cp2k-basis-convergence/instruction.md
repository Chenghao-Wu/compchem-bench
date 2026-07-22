# Task: Basis-Set Convergence of the Methanol Energy (CP2K)

## Background

Study the convergence of the DFT total energy of methanol (CH3OH) with
respect to basis-set size using CP2K's MOLOPT basis series.

## Your Task

The geometry `methanol.xyz` is provided in `/workspace/assets/`. Run
**three single-point energy calculations** on this exact geometry with the
PBE functional, differing **only** in the basis set:

1. `SZV-MOLOPT-GTH`
2. `DZVP-MOLOPT-GTH`
3. `TZVP-MOLOPT-GTH`

All other settings must be identical across the three runs:

- `GTH-PBE` pseudopotentials (`GTH-PBE-q4` for C, `GTH-PBE-q6` for O,
  `GTH-PBE-q1` for H)
- plane-wave cutoff 300 Ha with `REL_CUTOFF 60`
- 10 Å cubic non-periodic box (`PERIODIC NONE`)
- `EPS_SCF 1.0E-7`, `MAX_SCF 50`, `SCF_GUESS ATOMIC`
- `RUN_TYPE ENERGY`

The basis-set and pseudopotential data files (`BASIS_MOLOPT`,
`GTH_POTENTIALS`) are part of the CP2K installation at `/opt/cp2k/data/` —
copy or symlink them into your working directory (inputs reference them by
bare filename).

Save the three outputs as `methanol_szv.out`, `methanol_dzvp.out`, and
`methanol_tzvp.out` in `/workspace/` — all three are needed for
verification.

Then write `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "energy_szv": <float, Ha>,
    "energy_dzvp": <float, Ha>,
    "energy_tzvp": <float, Ha>,
    "monotonic_decreasing": <bool>
  },
  "units": {
    "energy_szv": "Ha",
    "energy_dzvp": "Ha",
    "energy_tzvp": "Ha",
    "monotonic_decreasing": "1"
  }
}
```

`monotonic_decreasing` is true if the total energy decreases monotonically
as the basis set grows (SZV > DZVP > TZVP in value, i.e. each successively
more negative).

## Requirements

- Use the exact geometry from `/workspace/assets/methanol.xyz` for all
  three runs (do not modify it — the verifier checksums the asset).
- Parse the **actual** CP2K outputs — do not hardcode energies. The
  verifier checks each output for the CP2K banner, SCF convergence, normal
  termination, and that the geometry in the log matches the asset; it
  re-runs the cheapest (SZV) point itself and requires it to agree with
  your SZV log and `results.json`.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/methanol.xyz`
- Basis/pseudopotentials are in `/opt/cp2k/data/` (accessible inside the container)
- Output: `methanol_szv.out`, `methanol_dzvp.out`, `methanol_tzvp.out`,
  `results.json` in `/workspace/`

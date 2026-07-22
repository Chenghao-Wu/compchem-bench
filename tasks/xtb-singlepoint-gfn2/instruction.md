# Task: GFN2-xTB Single-Point Energy of Acetonitrile (xtb)

## Background

Run a GFN2-xTB semi-empirical single-point calculation on acetonitrile
(CH3CN) and report the total energy and the HOMO–LUMO gap.

## Your Task

The geometry `acetonitrile.xyz` is provided in `/workspace/assets/`. Run
xtb with the GFN2 Hamiltonian in single-point mode (no optimization) on
this exact geometry, saving the full standard output to `xtb_sp.out` in
`/workspace/`:

```bash
xtb acetonitrile.xyz --gfn 2 > xtb_sp.out 2>&1
```

Then parse `xtb_sp.out` and write `results.json` in the standard
CompChemBench schema:

```json
{
  "values": {
    "total_energy": <float, Eh>,
    "homo_lumo_gap": <float, eV>
  },
  "units": {
    "total_energy": "Eh",
    "homo_lumo_gap": "eV"
  }
}
```

## Requirements

- Use the exact geometry from `/workspace/assets/acetonitrile.xyz` (do
  not modify it — the verifier checksums the asset).
- Run in single-point mode: the geometry must not be optimized.
- Keep the run's stdout in `xtb_sp.out` — it is needed for verification.
- Do **not** hardcode the energy or gap — the verifier re-runs the same
  single point itself and requires its result to agree with your log and
  your `results.json`.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/acetonitrile.xyz`
- Output: `xtb_sp.out`, `results.json` in `/workspace/`

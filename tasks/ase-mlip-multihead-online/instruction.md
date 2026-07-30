# Task: Bootstrap and Run Universal MLIPs

## Background

You have two structure files and internet access. Your job is to prepare the
missing CPU software environment and model checkpoints, then compute
**single-point energies** (raw model output, no empirical dispersion
corrections) for each structure with each model.

## The Structures

The `assets/` directory contains two input files:

| File | Origin | Description |
|---|---|---|
| `mol_structure.xyz` | **Transition1x** dataset | Organic molecule, isolated (no periodic boundary conditions) |
| `surf_structure.cif` | **OC20-NEB** benchmark | Catalytic surface slab with adsorbate, periodic in all directions |

Familiarity with these benchmark names may be helpful when configuring the models.

## The Models

Use exactly these two universal MLIPs:

1. **MatterSim-v1.0.0-5M**
2. **DPA-3.2-5M**

The container initially provides CPU-only PyTorch and basic download tools,
but it does not provide the Python packages or model checkpoints needed to
run these MLIPs. Discover and install the required packages into the active
Python environment, and download the two checkpoints yourself.

Save the checkpoints at these fixed locations so the final state can be
verified:

- `/workspace/models/DPA-3.2-5M.pt`
- `/workspace/models/mattersim-v1.0.0-5M.pth`

## Your Task

For **each** of the two structures, compute the **raw single-point energy**
with **both** models. Do **not** apply any dispersion correction (no D3, no
DFT-D, no vdW). Use the model output as-is.

Write the results to `results.json` in the following schema:

```json
{
  "values": {
    "dpa3_mol_energy_eV": <float>,
    "mattersim_mol_energy_eV": <float>,
    "dpa3_surf_energy_eV": <float>,
    "mattersim_surf_energy_eV": <float>
  },
  "units": {
    "dpa3_mol_energy_eV": "eV",
    "mattersim_mol_energy_eV": "eV",
    "dpa3_surf_energy_eV": "eV",
    "mattersim_surf_energy_eV": "eV"
  }
}
```

## Requirements

- **Do not** hardcode the answers — run the actual calculations. The
  verifier independently recomputes and cross-checks.
- **Do not** apply any dispersion correction. Use raw MLIP energies only.
- Use the structure files exactly as provided in `assets/`.
- The `surf_structure.cif` is a periodic system; handle cell vectors and
  PBC correctly.
- `results.json` must be valid JSON. Every key in `values` must appear in
  `units`.
- All calculations must use CPU-only PyTorch. Do not install CUDA-enabled
  wheels or use GPU devices.

## Hints

- Some universal MLIPs have different internal heads or branches for
  different chemical domains. What do you know about the datasets these
  structures came from?
- The model documentation and API signatures are the authoritative source
  for configuration options.
- You can run on CPU for this task — only two single-point evaluations
  per model are needed.

## Files

Your working directory is `/workspace`. The structure files are at
`/workspace/assets/`. Write all output to `/workspace`.

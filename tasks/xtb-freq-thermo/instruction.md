# Task: GFN2-xTB Vibrational Frequencies and Thermochemistry of Ethanol (xtb)

## Background

Run a GFN2-xTB geometry optimization followed by a numerical Hessian
(vibrational frequency) calculation on ethanol (C2H5OH), and report the
thermochemical quantities at 298.15 K.

## Your Task

The starting geometry `ethanol.xyz` is provided in `/workspace/assets/`.
Run xtb with the GFN2 Hamiltonian in combined optimization + Hessian mode
from `/workspace/`, saving the full standard output to `xtb_thermo.out`:

```bash
xtb ethanol.xyz --gfn 2 --ohess > xtb_thermo.out 2>&1
```

After the run completes:

1. Keep in `/workspace/` the optimized geometry `xtbopt.xyz` and the
   frequency file `vibspectrum` (both written by xtb) — they are needed
   for verification.
2. Parse `xtb_thermo.out` to extract from the final thermochemistry
   summary block:
   - `total energy` (electronic energy at the optimized geometry)
   - `zero point energy` (ZPE)
   - `total free energy` (G at 298.15 K, including ZPE)
   - the number of imaginary frequencies
3. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "total_energy": <float, Eh>,
       "zpe": <float, Eh>,
       "free_energy_298": <float, Eh>,
       "n_imaginary_freqs": <int>
     },
     "units": {
       "total_energy": "Eh",
       "zpe": "Eh",
       "free_energy_298": "Eh",
       "n_imaginary_freqs": "1"
     }
   }
   ```

## Requirements

- The optimization must converge (`GEOMETRY OPTIMIZATION CONVERGED`) and
  the Hessian must show **no imaginary frequencies** (all 3N−6 genuine
  vibrational modes positive).
- Do **not** hardcode any value — the verifier (a) runs its own
  single-point calculation on your `xtbopt.xyz` and requires it to agree
  with your reported total energy, and (b) independently recomputes the
  ZPE from the frequency table in your `vibspectrum` file and requires it
  to agree with your reported ZPE.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/ethanol.xyz`
- Output: `xtb_thermo.out`, `xtbopt.xyz`, `vibspectrum`, `results.json`
  in `/workspace/`

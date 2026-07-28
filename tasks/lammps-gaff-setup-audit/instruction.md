# Task: Audit a GAFF2 Force-Field Setup (LAMMPS)

## Background

An input script that runs without error is not the same as an input script
that computes what you meant. A force field is a *package*: the functional
forms, the parameters, **and** the non-bonded conventions that go with them.
Drop one of those conventions and LAMMPS will happily run to completion and
report a clean, plausible-looking energy for a force field nobody
parameterised.

## Your Task

`/workspace/assets/` contains a single-point energy calculation on a porphin
molecule (C20H14N4, 40 atoms, net neutral) with the GAFF2 force field:

- `porphin_energy.in` — the input script, as written
- `system_gaff2.data` — LAMMPS data file (topology + coordinates)
- `system_gaff2.in.settings` — GAFF2 coefficients

The script runs cleanly and prints a full energy decomposition. **The setup
is nevertheless wrong.** It omits one setting that GAFF2 requires — GAFF2
inherits the non-bonded conventions of the AMBER family it was derived
from — and without it the reported energy is not a GAFF2 energy.

The omission does not affect the bonded terms. It changes the non-bonded
ones.

Other choices in this input are arguable — the cutoff and switching scheme,
the size of the periodic box around a single molecule — and a thorough
review might well raise them. They are deliberately **out of scope** here:
none of them makes the energy wrong for the model as declared, and changing
any of them will fail this task. Fix the omission, and only the omission.

1. Copy the input to `/workspace/`, run it as shipped, and keep that log as
   `/workspace/log_original.lammps`.
2. Identify the missing setting. Produce a corrected input
   `/workspace/energy_audited.in` that adds it and changes **nothing else** —
   same styles, same cutoffs, same k-space solver, same data and settings
   files, read by the same relative `assets/...` paths.
3. Run the corrected input, keeping its log as
   `/workspace/log_audited.lammps`. Keep its thermo output at least as
   detailed as the original's.
4. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "e_pot_original": <float>,
       "e_vdwl_original": <float>,
       "e_coul_original": <float>,
       "e_pot_audited": <float>,
       "e_vdwl_audited": <float>,
       "e_coul_audited": <float>,
       "delta_e_pot": <float>,
       "lj_14_scale": <float>,
       "coul_14_scale": <float>
     },
     "units": {
       "e_pot_original": "kcal/mol",
       "e_vdwl_original": "kcal/mol",
       "e_coul_original": "kcal/mol",
       "e_pot_audited": "kcal/mol",
       "e_vdwl_audited": "kcal/mol",
       "e_coul_audited": "kcal/mol",
       "delta_e_pot": "kcal/mol",
       "lj_14_scale": "1",
       "coul_14_scale": "1"
     }
   }
   ```

   - `*_original` — from the script as shipped
   - `*_audited` — from your corrected script
   - `delta_e_pot` — `e_pot_audited - e_pot_original`
   - `lj_14_scale`, `coul_14_scale` — the **1-4 scaling factors your
     correction applies**, as plain numbers (report the values you actually
     used, not a keyword)

## Requirements

- Fix only what is missing. The verifier checks that the bonded terms
  (`ebond`, `eangle`, `edihed`, `eimp`) are **bit-for-bit identical** between
  your two runs — a correction that perturbs them has changed the physics
  rather than completed the force field.
- Parse the **actual** logs — do not hardcode energies. The verifier
  validates the shipped assets by sha256, checks both logs for the banner,
  the completion footer and a genuine zero-step run on 40 atoms, and
  requires `results.json` to match your own logs.
- As the decisive check, the verifier **independently re-runs both the
  original and the corrected single point** with the in-image LAMMPS and
  requires every energy you report to match its own result.
- `results.json` must be valid JSON following the schema above: every key in
  `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/porphin_energy.in`,
  `/workspace/assets/system_gaff2.data`,
  `/workspace/assets/system_gaff2.in.settings`
- Output: `energy_audited.in`, `log_original.lammps`, `log_audited.lammps`,
  `results.json` in `/workspace/`

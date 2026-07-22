# Task: Write a vc-relax Input for Zinc-Blende SiC (Quantum ESPRESSO)

## Background

Variable-cell relaxation (`calculation = 'vc-relax'`) with `pw.x` relaxes both
the ionic positions and the unit cell. Writing a correct, runnable vc-relax
input deck is a core DFT workflow skill: the plane-wave cutoff, the SCF and
force convergence criteria, and the k-point sampling all have to be chosen
deliberately, and the input must be syntactically and semantically valid for
`pw.x` to run it at all.

## Your Task

The crystal structure of silicon carbide in the zinc-blende (3C) phase is
provided as `/workspace/assets/sic.cif` (conventional cubic cell, Si at the
4a and C at the 4c Wyckoff positions). The
pseudopotentials to use are in `/workspace/assets/pseudo/`.

Write a complete `pw.x` input file at **`/workspace/sic_vc_relax.in`** for a
variable-cell relaxation of this structure. The input must satisfy ALL of the
following requirements:

1. **Calculation type**: `calculation = 'vc-relax'`.
2. **Structure**: the 2-atom primitive cell of zinc-blende SiC — Si at
   crystal coordinate (0, 0, 0) and C at (1/4, 1/4, 1/4) of the fcc primitive
   cell, with the lattice constant given in the CIF. You may express the cell
   in any valid
   form (`ibrav = 2` with `celldm(1)` or `A`, or `ibrav = 0` with
   `CELL_PARAMETERS`), and atomic positions in any valid unit.
3. **Pseudopotentials**: use exactly the two provided UPF files
   (`Si.pbe-n-rrkjus_psl.1.0.0.UPF` for Si, `C.pbe-n-kjpaw_psl.1.0.0.UPF`
   for C). You may point `pseudo_dir` at the assets directory or copy the
   files next to your input — either way the files must be present,
   correctly named, and byte-identical to the provided ones.
4. **Plane-wave cutoff**: `ecutwfc` of at least 40 Ry (choose an
   appropriate `ecutrho` for the pseudopotentials you are using).
5. **Convergence criteria**: SCF convergence threshold `conv_thr` of at
   most 1.0d-8, and force convergence threshold `forc_conv_thr` of at most
   1.0d-4.
6. **k-point sampling**: an automatic Monkhorst–Pack grid of at least
   4×4×4 (a denser grid is fine; any shift is fine).
7. The input must be **runnable**: the verifier executes a truncated
   (single-point) version of your exact input deck with the in-image
   `pw.x`. Any input error — unparsable cards, inconsistent namelist
   entries, missing settings your own deck requires — fails the task.

## Requirements

- Write only the input file (and, if you copy them, the pseudopotentials).
  You do **not** need to run the relaxation.
- Do not weaken the required thresholds: `conv_thr`, `forc_conv_thr`,
  `ecutwfc`, and the k-grid are checked semantically, and equivalent
  spellings (e.g. `1e-8` vs `1.0d-8`) are accepted.
- The structure in your deck is compared against the CIF reference; the
  lattice constant must match it tightly and the atomic arrangement must be
  the zinc-blende one (any overall translation is fine).

## Files

- Structure: `/workspace/assets/sic.cif`
- Pseudopotentials: `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`,
  `/workspace/assets/pseudo/C.pbe-n-kjpaw_psl.1.0.0.UPF`
- Output: `sic_vc_relax.in` in `/workspace/`

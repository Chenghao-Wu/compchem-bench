# Task: Band Structure of Silicon — scf → bands → bands.x (Quantum ESPRESSO)

## Background

Computing a band structure with Quantum ESPRESSO is a three-step workflow:

1. a self-consistent `pw.x` run (`calculation = 'scf'`) that produces the
   charge density,
2. a non-self-consistent `pw.x` run (`calculation = 'bands'`) that
   diagonalizes the Kohn–Sham Hamiltonian along a k-point path **reusing the
   charge density of step 1** (same `prefix` and `outdir`),
3. a post-processing run of `bands.x` that extracts and reorders the
   eigenvalues along the path.

## Your Task

Compute the band structure of crystalline silicon (diamond structure, 2-atom
primitive cell, `ibrav = 2` with `celldm(1) = 10.26`, Si at alat coordinates
(0,0,0) and (1/4,1/4,1/4), PBE) along the Γ→X line, using the provided
pseudopotential `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`.

**Step 1 — SCF.** `si_scf.in`: `calculation = 'scf'`, `ecutwfc = 40 Ry`,
`ecutrho = 320 Ry`, `conv_thr = 1.0d-10`, `K_POINTS automatic` `4 4 4 1 1 1`.
Run it and keep `si_scf.out`.

**Step 2 — bands.** `si_bands.in`: same cell, atoms, cutoffs and
pseudopotential; `calculation = 'bands'`; **the same `prefix` and `outdir` as
step 1** (the bands run must read the SCF charge density); `nbnd = 8`; the
k-point path Γ→X given in `tpiba` coordinates from (0, 0, 0) to (1, 0, 0)
with 20 intervals (21 k-points), using `K_POINTS tpiba_b`;
`conv_thr = 1.0d-10`. Run it and keep `si_bands.out` and the `outdir/`
directory.

**Step 3 — bands.x.** `bandsx.in`: `&BANDS` with the same `prefix`/`outdir`
and `filband = 'bands.dat'`. Run `bands.x` and keep `bandsx.out` and
`bands.dat`.

Silicon has 8 valence electrons per primitive cell, so bands 1–4 are occupied
and bands 5–8 are empty. From the band structure extract:

- the eigenvalues of **band 4** and **band 5** at **Γ** and at **X**,
- the valence-band maximum **VBM** (highest band-4 eigenvalue along the path),
- the conduction-band minimum **CBM** (lowest band-5 eigenvalue along the path),
- the **indirect band gap** CBM − VBM.

Write `results.json` in the standard CompChemBench schema (all eigenvalues in
eV, at least 3 decimal places):

```json
{
  "values": {
    "gamma_band4_eV": <float>,
    "gamma_band5_eV": <float>,
    "x_band4_eV": <float>,
    "x_band5_eV": <float>,
    "vbm_eV": <float>,
    "cbm_eV": <float>,
    "indirect_gap_eV": <float>
  },
  "units": {
    "gamma_band4_eV": "eV",
    "gamma_band5_eV": "eV",
    "x_band4_eV": "eV",
    "x_band5_eV": "eV",
    "vbm_eV": "eV",
    "cbm_eV": "eV",
    "indirect_gap_eV": "eV"
  }
}
```

## Requirements

- All three steps must actually run: the verifier inspects all three logs
  (version banners, settings echoes, `JOB DONE.`), checks that `si_scf.in`,
  `si_bands.in` and `bandsx.in` cross-reference the same `prefix`/`outdir`,
  parses `bands.dat`, and **independently re-derives every reported
  eigenvalue and the gap from the raw XML eigenvalues** in
  `outdir/pwscf.xml` — your `results.json` must agree with the XML, with
  `bands.dat`, and with the calibrated reference.
- Keep all seven files listed below in `/workspace/` exactly as `pw.x` /
  `bands.x` produced them.

## Files

- Pseudopotential: `/workspace/assets/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- Output: `si_scf.in`, `si_scf.out`, `si_bands.in`, `si_bands.out`,
  `bandsx.in`, `bandsx.out`, `bands.dat`, `outdir/`, `results.json` in
  `/workspace/`

# Task: Conformer Ensemble Generation and Butina Clustering (RDKit)

## Background

Conformer-ensemble analysis is a core molecular-modelling step: embed many
conformers, relax each with a force field, then cluster by RMSD to see how
many distinct conformational families the molecule actually populates. Here
you will do this for a small flexible molecule with a fully pinned,
reproducible pipeline.

## Your Task

The file `/workspace/assets/target.smi` contains the target molecule's
SMILES. Using RDKit (already installed), run **exactly** this pipeline:

1. Parse the SMILES and add explicit hydrogens (`Chem.AddHs`).
2. Embed **50** conformers with ETKDGv3 and the pinned seed so the ensemble
   is reproducible:

   ```python
   params = AllChem.ETKDGv3()
   params.randomSeed = 0xf00d  # 61453
   ids = AllChem.EmbedMultipleConfs(mol, numConfs=50, params=params)
   ```

   All 50 embeddings must succeed.
3. Optimize **every** conformer with the **MMFF94** force field
   (`AllChem.MMFFOptimizeMoleculeConfs(mol, mmffVariant="MMFF94",
   numThreads=1, maxIters=2000)`), and record the MMFF94 energy of each
   optimized conformer.
4. Compute the best-fit RMSD matrix over the optimized ensemble
   (`AllChem.GetConformerRMSMatrix(mol, prealigned=False)`) and cluster with
   the Butina algorithm at threshold **1.0 Å**:

   ```python
   from rdkit.ML.Cluster import Butina
   clusters = Butina.ClusterData(dmat, 50, 1.0, isDistData=True,
                                 reordering=True)
   ```
5. Write `conformers.sdf` in `/workspace/`: **one SDF record per optimized
   conformer, in conformer-id (embedding) order**
   (`SDWriter.write(mol, confId=cid)` for each of the 50 conformers).
6. Write `results.json` in the standard CompChemBench schema:

   ```json
   {
     "values": {
       "n_conformers": <int>,
       "n_clusters": <int>,
       "n_largest_cluster": <int>,
       "min_mmff_energy": <float, kcal/mol>
     },
     "units": {
       "n_conformers": "1",
       "n_clusters": "1",
       "n_largest_cluster": "1",
       "min_mmff_energy": "kcal/mol"
     }
   }
   ```

   - `n_conformers`: conformers in the ensemble (records in `conformers.sdf`)
   - `n_clusters`: Butina clusters
   - `n_largest_cluster`: size of the largest cluster
   - `min_mmff_energy`: lowest MMFF94 energy over the optimized ensemble

## Requirements

- Use **exactly** the pinned embedder/seed, MMFF94, and clustering settings
  above — the verifier independently: (a) recomputes the MMFF energy of
  every submitted conformer, (b) re-optimizes each one to confirm it is a
  true MMFF minimum, (c) re-computes the RMSD matrix from your SDF and
  re-clusters it, and (d) regenerates the reference ensemble from the
  pinned seed and matches energies conformer by conformer. Fabricated,
  un-optimized, or differently-seeded ensembles are rejected.
- `results.json` must be valid JSON following the schema above: every key
  in `values` must also appear in `units`.

## Files

- Input: `/workspace/assets/target.smi`
- Output: `conformers.sdf`, `results.json` in `/workspace/`

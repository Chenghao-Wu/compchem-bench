# ASE MLIP Multi-Head Offline Benchmark Task

This CompChemBench task evaluates whether an agent can select the correct
DPA-3.2-5M model head and compute raw single-point energies with DPA-3.2-5M
and MatterSim-v1.0.0-5M.

## Runtime

- CPU only; no CUDA-enabled PyTorch wheel is installed.
- Runtime networking is disabled.
- Both official checkpoints are downloaded during image construction and
  verified by SHA-256.
- `tests/` and `solution/` are not copied into the image.

## Build

From the task directory:

```bash
docker build \
  --platform=linux/amd64 \
  --file environment/Dockerfile \
  --tag compchem-bench/ase-mlip-multihead-offline:cpu \
  environment
```

## Oracle smoke test

Create a network-isolated CPU container, copy the oracle and verifier into it,
then run both:

```bash
cid=$(docker create --cpus=4 --memory=16g --network=none \
  --entrypoint=/bin/bash --workdir=/workspace \
  compchem-bench/ase-mlip-multihead-offline:cpu \
  -c 'bash /solution/solve.sh && bash /tests/test.sh')
docker cp solution "$cid:/solution"
docker cp tests "$cid:/tests"
docker start -a "$cid"
docker cp "$cid:/logs/verifier/reward.txt" ./reward.txt
docker rm -f "$cid"
```

`reward.txt` must contain `1`.

## Result contract

The agent writes `/workspace/results.json` with top-level `values` and `units`
objects. The four required values are:

- `dpa3_mol_energy_eV`
- `mattersim_mol_energy_eV`
- `dpa3_surf_energy_eV`
- `mattersim_surf_energy_eV`

All units are `eV`.

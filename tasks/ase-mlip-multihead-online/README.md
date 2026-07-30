# ASE MLIP Multi-Head Online Bootstrap Benchmark Task

This CompChemBench task evaluates whether an agent can bootstrap the missing
chemistry software and checkpoints over the network, select the correct
DPA-3.2-5M model head, and compute raw single-point energies with DPA-3.2-5M
and MatterSim-v1.0.0-5M.

## Runtime

- CPU only; the initial image contains the official CPU PyTorch stack.
- The agent/oracle phase has network access. The verifier phase is offline.
- ASE, DeepMD-kit, MatterSim, MPI and both checkpoints are absent initially.
- The agent installs the missing packages and saves both checkpoints under
  `/workspace/models/`.
- `tests/` and `solution/` are not copied into the image.

## Build

From the task directory:

```bash
docker build \
  --platform=linux/amd64 \
  --file environment/Dockerfile \
  --tag compchem-bench/ase-mlip-multihead-online:cpu \
  environment
```

## Oracle smoke test

Create a CPU container with the default bridge network, run the online oracle,
disconnect networking, and then run the verifier:

```bash
cid=$(docker create --cpus=4 --memory=16g --network=bridge \
  --entrypoint=/bin/bash --workdir=/workspace \
  compchem-bench/ase-mlip-multihead-online:cpu \
  -c 'sleep infinity')
docker cp solution "$cid:/solution"
docker cp tests "$cid:/tests"
docker start "$cid"
docker exec "$cid" bash /solution/solve.sh
docker network disconnect bridge "$cid"
docker exec "$cid" bash /tests/test.sh
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

#!/usr/bin/env bash
# Oracle solution for ase-mlip-multihead-offline.
set -euo pipefail

WORKSPACE="${1:-/workspace}"
mkdir -p "$WORKSPACE"

WORKSPACE="$WORKSPACE" python <<'PY'
import json
import os

import torch
from ase.io import read
from deepmd.calculator import DP
from mattersim.forcefield import MatterSimCalculator

assert torch.version.cuda is None, f"Expected CPU-only torch, got CUDA {torch.version.cuda}"
assert not torch.cuda.is_available(), "CUDA must not be available"

workspace = os.environ["WORKSPACE"]
assets = os.path.join(workspace, "assets")
dpa_model = "/opt/models/DPA-3.2-5M.pt"
mattersim_model = "/opt/models/mattersim-v1.0.0-5M.pth"

values = {}

atoms = read(os.path.join(assets, "mol_structure.xyz"))
atoms.calc = DP(model=dpa_model, head="OMol25")
values["dpa3_mol_energy_eV"] = float(atoms.get_potential_energy())

atoms = read(os.path.join(assets, "mol_structure.xyz"))
atoms.calc = MatterSimCalculator(load_path=mattersim_model, device="cpu")
values["mattersim_mol_energy_eV"] = float(atoms.get_potential_energy())

atoms = read(os.path.join(assets, "surf_structure.cif"), format="cif")
atoms.calc = DP(model=dpa_model, head="OC20M")
values["dpa3_surf_energy_eV"] = float(atoms.get_potential_energy())

atoms = read(os.path.join(assets, "surf_structure.cif"), format="cif")
atoms.calc = MatterSimCalculator(load_path=mattersim_model, device="cpu")
values["mattersim_surf_energy_eV"] = float(atoms.get_potential_energy())

results = {
    "values": values,
    "units": {key: "eV" for key in values},
}
path = os.path.join(workspace, "results.json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(results, handle, indent=2)

print(json.dumps(results, indent=2))
PY

#!/usr/bin/env bash
# Oracle solution for ase-mlip-multihead-online.
set -euo pipefail

WORKSPACE="${1:-/workspace}"
mkdir -p "$WORKSPACE"

python -m pip install \
    "ase==3.26.0" \
    "deepmd-kit==3.1.3" \
    "mattersim==1.2.2"
python -m pip install --no-deps \
    "numpy==2.4.6" \
    "mpich==5.0.1"
python -m pip check

MODELS_DIR="$WORKSPACE/models"
mkdir -p "$MODELS_DIR"
curl -fL --retry 5 \
    "https://modelscope.cn/models/DeepModelingCommunity/DPA-3.2-5M/resolve/master/DPA-3.2-5M.pt" \
    -o "$MODELS_DIR/DPA-3.2-5M.pt"
echo "876354744aeaae17b2639a6a690514470273784f2b4836280850f50cbb799165  $MODELS_DIR/DPA-3.2-5M.pt" \
    | sha256sum -c -
curl -fL --retry 5 \
    "https://raw.githubusercontent.com/microsoft/mattersim/v1.2.2/pretrained_models/mattersim-v1.0.0-5M.pth" \
    -o "$MODELS_DIR/mattersim-v1.0.0-5M.pth"
echo "e3df9fa708725e3d453140646c7d1838324b347a3d1214cf1440522146f872b5  $MODELS_DIR/mattersim-v1.0.0-5M.pth" \
    | sha256sum -c -

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
dpa_model = os.path.join(workspace, "models", "DPA-3.2-5M.pt")
mattersim_model = os.path.join(
    workspace, "models", "mattersim-v1.0.0-5M.pth"
)

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

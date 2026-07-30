#!/usr/bin/env python3
"""Verifier for the ASE MLIP multi-head benchmark task."""

import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_KEYS = [
    "dpa3_mol_energy_eV",
    "mattersim_mol_energy_eV",
    "dpa3_surf_energy_eV",
    "mattersim_surf_energy_eV",
]


def fail(message: str) -> None:
    print(f"VERIFY FAIL: {message}")
    raise SystemExit(1)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def run_python(code: str) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as handle:
        handle.write(code)
        script_path = handle.name
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy(),
            check=False,
        )
        if result.returncode != 0:
            fail(
                "Independent recompute failed:\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        for line in reversed(result.stdout.splitlines()):
            if line.strip().startswith("{"):
                return json.loads(line)
        fail(f"No JSON result from independent recompute:\n{result.stdout}")
    finally:
        os.unlink(script_path)


def main() -> None:
    workspace = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/workspace")
    script_dir = Path(__file__).resolve().parent
    assets_dir = os.path.join(workspace, "assets")

    with open(script_dir / "refs.json", encoding="utf-8") as handle:
        refs = json.load(handle)

    print("=" * 60)
    print("CompChemBench Verifier: ase-mlip-multihead-offline")
    print("=" * 60)

    import torch

    if torch.version.cuda is not None or torch.cuda.is_available():
        fail("Verifier requires a CPU-only PyTorch runtime")

    print("\n[L0] Asset integrity...")
    for relative_path, expected_hash in refs["asset_hashes"].items():
        asset_path = os.path.join(workspace, relative_path)
        if not os.path.isfile(asset_path):
            fail(f"Asset not found: {asset_path}")
        actual_hash = sha256_file(asset_path)
        if actual_hash != expected_hash:
            fail(
                f"Asset hash mismatch for {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        print(f"  OK  {relative_path}")

    print("\n[L0b] Model integrity...")
    for model_path, expected_hash in refs["model_hashes"].items():
        if not os.path.isfile(model_path):
            fail(f"Model checkpoint not found: {model_path}")
        actual_hash = sha256_file(model_path)
        if actual_hash != expected_hash:
            fail(
                f"Model hash mismatch for {model_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        print(f"  OK  {model_path}")

    results_path = os.path.join(workspace, "results.json")
    if not os.path.isfile(results_path):
        fail(f"results.json not found at {results_path}")
    with open(results_path, encoding="utf-8") as handle:
        try:
            results = json.load(handle)
        except json.JSONDecodeError as exc:
            fail(f"results.json is not valid JSON: {exc}")

    if "values" not in results or "units" not in results:
        fail("results.json must contain values and units objects")
    values = results["values"]
    units = results["units"]
    for key in REQUIRED_KEYS:
        if key not in values or key not in units:
            fail(f"results.json missing {key}")
        if not isinstance(values[key], (int, float)) or not math.isfinite(values[key]):
            fail(f"values.{key} must be a finite number")
        if units[key] != "eV":
            fail(f"units.{key} must be eV")

    dpa_code = f'''
import json
import os
import torch
from ase.io import read
from deepmd.calculator import DP
assert torch.version.cuda is None and not torch.cuda.is_available()
assets = {assets_dir!r}
model = {refs["dpa_model_path"]!r}
values = {{}}
atoms = read(os.path.join(assets, "mol_structure.xyz"))
atoms.calc = DP(model=model, head={refs["dpa_molecule_head"]!r})
values["dpa3_mol_energy_eV"] = float(atoms.get_potential_energy())
atoms = read(os.path.join(assets, "surf_structure.cif"), format="cif")
atoms.calc = DP(model=model, head={refs["dpa_surface_head"]!r})
values["dpa3_surf_energy_eV"] = float(atoms.get_potential_energy())
print(json.dumps(values))
'''
    mattersim_code = f'''
import json
import os
import torch
from ase.io import read
from mattersim.forcefield import MatterSimCalculator
assert torch.version.cuda is None and not torch.cuda.is_available()
assets = {assets_dir!r}
model = {refs["mattersim_model_path"]!r}
values = {{}}
atoms = read(os.path.join(assets, "mol_structure.xyz"))
atoms.calc = MatterSimCalculator(load_path=model, device="cpu")
values["mattersim_mol_energy_eV"] = float(atoms.get_potential_energy())
atoms = read(os.path.join(assets, "surf_structure.cif"), format="cif")
atoms.calc = MatterSimCalculator(load_path=model, device="cpu")
values["mattersim_surf_energy_eV"] = float(atoms.get_potential_energy())
print(json.dumps(values))
'''

    print("\n[L1] Independent CPU recompute...")
    recomputed = {**run_python(dpa_code), **run_python(mattersim_code)}
    cross_tolerance = refs.get("cross_verify_atol", 0.001)
    for key in REQUIRED_KEYS:
        difference = abs(values[key] - recomputed[key])
        if difference > cross_tolerance:
            fail(
                f"Cross-verify mismatch for {key}: "
                f"agent={values[key]}, recomputed={recomputed[key]}, diff={difference}"
            )
        print(f"  OK  {key}: diff={difference:.3e}")

    print("\n[L2] Calibrated references...")
    for key in REQUIRED_KEYS:
        reference = refs[f"{key}_ref"]
        tolerance = refs[f"{key}_tol"]
        difference = abs(values[key] - reference)
        if difference > tolerance:
            fail(
                f"Reference mismatch for {key}: "
                f"value={values[key]}, reference={reference}, diff={difference}, "
                f"tolerance={tolerance}"
            )
        print(f"  OK  {key}: diff={difference:.3e}")

    print("\nALL VERIFICATION CHECKS PASSED")


if __name__ == "__main__":
    main()

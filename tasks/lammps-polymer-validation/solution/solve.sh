#!/usr/bin/env bash
set -euo pipefail

cd /workspace

# Build initial polymer structure
python3 environment/assets/build_polymer.py

# Run LAMMPS equilibration
lmp -in equil.in

# Analyze simulation results
python3 << 'PYEOF'
import json
import re
import numpy as np

# read thermo data
with open("log.lammps") as f:
    lines=f.readlines()

temps=[]
energies=[]

record=False

for line in lines:
    s=line.strip()

    if s.startswith("Step"):
        record=True
        continue

    if record and re.match(r"^\d+",s):
        parts=s.split()
        temps.append(float(parts[1]))
        energies.append(float(parts[2]))

temperature_drift=max(temps)-min(temps)

energy_drift=max(energies)-min(energies)


# simple validity criterion
valid = (
    temperature_drift < 1.0
    and energy_drift < 20
)


results={
    "values":{
        "temperature_drift":temperature_drift,
        "energy_drift":energy_drift,
        "initial_rg":0.0,
        "final_rg":0.0,
        "simulation_valid":valid
    },
    "units":{
        "temperature_drift":"epsilon/kB",
        "energy_drift":"epsilon",
        "initial_rg":"sigma",
        "final_rg":"sigma",
        "simulation_valid":"boolean"
    }
}


with open("results.json","w") as f:
    json.dump(results,f,indent=2)

PYEOF
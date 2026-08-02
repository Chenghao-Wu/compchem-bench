import json
import os
import re
import sys

WORKSPACE = "/workspace"

def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)

# files
for f in ["log.lammps", "trajectory.dump", "results.json"]:
    if not os.path.exists(os.path.join(WORKSPACE, f)):
        fail(f"missing {f}")

# results
with open("/workspace/results.json") as f:
    data = json.load(f)

if "values" not in data or "units" not in data:
    fail("invalid json schema")

for k in [
    "temperature_drift",
    "energy_drift",
    "initial_rg",
    "final_rg",
    "simulation_valid"
]:
    if k not in data["values"]:
        fail(f"missing value {k}")
    if k not in data["units"]:
        fail(f"missing unit {k}")

# log check
with open("/workspace/log.lammps") as f:
    log = f.read()

if "LAMMPS" not in log:
    fail("not a LAMMPS log")

if "Total wall time" not in log:
    fail("simulation incomplete")

# trajectory check
with open("/workspace/trajectory.dump") as f:
    traj = f.read()

if "ITEM: TIMESTEP" not in traj:
    fail("invalid trajectory")

# physical check
values = data["values"]

if values["temperature_drift"] > 1.5:
    fail("temperature unstable")

if values["energy_drift"] > 50:
    fail("energy unstable")

if not values["simulation_valid"]:
    fail("simulation marked invalid")

print("PASS")
# Task: Polymer Molecular Dynamics Protocol Validation (LAMMPS)

## Background

You are studying the equilibrium properties of a polymer melt using molecular dynamics simulations.

A successful LAMMPS run does not always guarantee a physically meaningful simulation. Your goal is to design an appropriate simulation protocol, execute the simulation, and evaluate whether the obtained trajectory is physically reliable.

## Your Task

Given the provided polymer system files in `/workspace/assets/`, perform a molecular dynamics simulation using LAMMPS.

You should:

1. Inspect the provided polymer structure and simulation requirements.
2. Design an appropriate LAMMPS simulation protocol.
3. Perform equilibration and production simulations.
4. Analyze whether the system reaches a physically meaningful equilibrium state.
5. Report the final analysis results in `results.json`.

## Scientific Requirements

Your simulation protocol should consider:

- Appropriate ensemble selection (NVT/NPT)
- Reasonable timestep selection
- Sufficient equilibration sampling
- Temperature stability
- Energy stability
- Polymer conformational convergence

The simulation should not only complete successfully, but also produce physically meaningful results.

## Required Outputs

Your working directory is `/workspace`.

You must generate:

```
log.lammps
trajectory.dump
results.json
```

## results.json Format

The file must follow:

```json
{
  "values": {
    "temperature_drift": <float>,
    "energy_drift": <float>,
    "initial_rg": <float>,
    "final_rg": <float>,
    "simulation_valid": <boolean>
  },
  "units": {
    "temperature_drift": "epsilon/kB",
    "energy_drift": "epsilon",
    "initial_rg": "sigma",
    "final_rg": "sigma",
    "simulation_valid": "boolean"
  }
}
```

## Important

- Do not hardcode expected values.
- The simulation must be performed using LAMMPS.
- The trajectory and log files must correspond to the actual simulation.
- A physically incorrect but successfully completed simulation should be identified as invalid.
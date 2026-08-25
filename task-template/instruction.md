<!--
  Authoring notes — DELETE before shipping. This is the ONLY agent-visible
  file; it must contain NO reference values and NO solution procedure.

  Style (see .claude/skills/compchem-instruction-writer/SKILL.md):
    * concise, goal-oriented, not tutorial-like
    * state the scientific objective + exact task contract, not the workflow
    * exact where grading needs determinism; open where judgment is the skill
    * never name a planted fault / silent error, nor how the verifier catches
      cheating (use "outputs will be checked for numerical consistency" at most)

  Lint: if this file contains "results.json" (it does, below), it MUST show the
  {"values": {...}, "units": {...}} schema, and verify.py MUST read
  results["values"] / results["units"].

  Do NOT put numeric reference values here (lint flags e.g. "-76.3 Ha").
-->

# Task: <Scientific task title>

<1–3 short paragraphs: the system, the available inputs, and the scientific
objective. Example:>

Use the Atomic Simulation Environment (ASE) to geometry-optimize a water
molecule. The calculator is fixed for this task so results are reproducible
and independently checkable.

Inputs are available at:

- `/workspace/assets/<...>`   <-- list every input path the agent receives;

<State the task in plain scientific prose. Include exact selections,
conditions, grids, windows, or numerical settings ONLY when they define the
target. Example:>

Create a water molecule (H2O), attach exactly this calculator:

```python
from ase.calculators.lj import LennardJones
mol.calc = LennardJones(epsilon=0.01, sigma=1.0, rc=5.0)
```

Run a geometry optimization until the maximum force on any atom is below
**0.05 eV/Å**, and write the trajectory to `opt.traj`.

## Deliverables

Write the required outputs to `/workspace/`:

- `<output file, exact name>`
- `results.json` in the standard CompChemBench schema:

```json
{
  "values": {
    "<key>": <value>,
    "<key>": <value>
  },
  "units": {
    "<key>": "<unit>",
    "<key>": "<unit>"
  }
}
```

<Define each `values` key precisely (what it means, its unit). Every key in
`values` must also appear in `units`.>

## Requirements

- <immutable scientific constraint — e.g. exact calculator / functional /
  settings that must not change>
- <reproducibility constraint — e.g. "run the actual calculation; do not
  hardcode the answer">
- <validity constraint — e.g. "outputs must come from converged calculations
  and be consistent with the submitted geometries">

## Files

Your working directory is `/workspace`. Write all output there.

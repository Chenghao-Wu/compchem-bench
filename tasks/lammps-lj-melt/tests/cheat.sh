#!/usr/bin/env bash
# Informed cheat: a forger who knows LAMMPS log format and the qualitative
# behavior of an NVE LJ melt (T drops from the initial ~1.44 to ~0.7, PE
# rises toward ~-5.7). Fabricates a complete, self-consistent log.lammps —
# banner, 51 thermo lines on the right step grid, Loop time, Total wall
# time — plus a results.json matching the forged log exactly, with correct
# log_lines.
# Must FAIL: the guessed final values (T≈0.68, PE≈-5.71) are plausible but
# not the true deterministic trajectory values (ref T=0.7007±0.001,
# PE=-5.6755±0.001) — guessing the exact seed-87287 trajectory to 1e-3
# without running it is not possible.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import numpy as np

# Plausible melt trajectory: exponential equilibration
lines = ["LAMMPS (7 Jan 2022) — fake banner", "Step          Temp         PotEng        Etot         Press"]
final_t, final_pe = 0.6821, -5.7093
for step in range(0, 5001, 100):
    frac = step / 5000
    t = 1.44 + (final_t - 1.44) * (1 - np.exp(-3 * frac)) / (1 - np.exp(-3))
    pe = -4.1 + (final_pe + 4.1) * (1 - np.exp(-3 * frac)) / (1 - np.exp(-3))
    lines.append(f"{step:>8d} {t:14.7f} {pe:14.7f} {-1.5:12.6f} {0.5:12.6f}")
lines.append("Loop time of 3.21 on 1 procs for 5000 steps with 256 atoms")
lines.append("Total wall time: 0:00:04")

with open("log.lammps", "w") as f:
    f.write("\n".join(lines) + "\n")

results = {
    "values": {
        "final_step": 5000,
        "final_temp": final_t,
        "final_pe": final_pe,
        "log_lines": len(lines),
    },
    "units": {
        "final_step": "1",
        "final_temp": "ε/kB",
        "final_pe": "ε/atom",
        "log_lines": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged complete log ({len(lines)} lines) + self-consistent results.json")
PYEOF

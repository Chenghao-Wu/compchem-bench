#!/usr/bin/env bash
# Informed cheat: a forger who knows CP2K MD output formats and NVE
# phenomenology. Fabricates:
#   - h2o_aimd.out with banner + normal-termination footer
#   - h2o_aimd-1.ener with exactly 21 rows (steps 0..20, 0.5 fs), fully
#     self-consistent (Cons Qty == Kin + Pot per row, tiny drift) at a
#     plausible potential energy around the equilibrium value
#   - h2o_aimd-pos-1.xyz with 21 frames ending at the INITIAL equilibrium
#     geometry (easy to construct — it is in the provided input)
#   - results.json self-consistent with the forged .ener
# Passes layers 1-4 (existence, banner/footer, .ener shape and internal
# consistency, log<->results consistency).
# Must FAIL later: the guessed potential energy is not the true
# deterministic trajectory value (reference tolerance 1e-6 Ha), AND the
# verifier's real single point on the forged final frame (equilibrium
# geometry, not the true thermalized step-20 geometry) returns the
# equilibrium energy — not the claimed value — breaking three-way
# agreement at layer 7.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json
import math

fake_pot0 = -17.21966      # equilibrium-ish potential energy guess
fake_pot_final = -17.21980  # plausible thermalized final value

# .ener: 21 rows, Cons == Kin + Pot exactly, drift ~2e-6
lines = ["#     Step Nr.          Time[fs]        Kin.[a.u.]          Temp[K]            Pot.[a.u.]        Cons Qty[a.u.]        UsedTime[s]"]
for i in range(21):
    t = 0.5 * i
    temp = 300.0 + 40.0 * math.sin(i * 0.9)
    kin = temp * 4.7507e-6          # ~ (3/2) kB T in Hartree
    pot = fake_pot0 + (fake_pot_final - fake_pot0) * (i / 20.0)
    cons = -17.2182300 - 2.0e-6 * (i / 20.0)
    kin = cons - pot                # enforce Cons == Kin + Pot
    temp = kin / 4.7507e-6
    lines.append(f"{i:10d} {t:15.6f} {kin:18.9f} {temp:18.9f} {pot:18.9f} {cons:18.9f} {1.87:18.6f}")
with open("h2o_aimd-1.ener", "w") as f:
    f.write("\n".join(lines) + "\n")

# .out: banner + footer
with open("h2o_aimd.out", "w") as f:
    f.write("****  ****  CP2K version 2024.1 (fake banner)  ****  ****\n")
    f.write(" PROGRAM STARTED AT 2026-07-20 00:00:00.000\n")
    f.write(" ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:              -17.2196600000\n")
    f.write(" PROGRAM ENDED AT 2026-07-20 00:01:00.000\n PROGRAM STOPPED IN /workspace\n")

# xyz: 21 frames of the initial equilibrium geometry (from the provided input)
coords = [("O", 0.000000, 0.000000, 0.117362),
          ("H", 0.000000, 0.757210, -0.469448),
          ("H", 0.000000, -0.757210, -0.469448)]
with open("h2o_aimd-pos-1.xyz", "w") as f:
    for i in range(21):
        f.write("3\n")
        f.write(f" i =        {i}, E =      {fake_pot0:.10f}\n")
        for sym, x, y, z in coords:
            f.write(f" {sym}        {x:15.10f}   {y:15.10f}   {z:15.10f}\n")

pots = [float(l.split()[4]) for l in lines[1:]]
temps = [float(l.split()[3]) for l in lines[1:]]
cons = [float(l.split()[5]) for l in lines[1:]]
results = {
    "values": {
        "final_potential": pots[-1],
        "mean_temperature": sum(temps) / len(temps),
        "cons_qty_drift": abs(cons[-1] - cons[0]),
        "n_md_steps": 20,
    },
    "units": {
        "final_potential": "Ha",
        "mean_temperature": "K",
        "cons_qty_drift": "Ha",
        "n_md_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged .ener (21 self-consistent rows) + equilibrium-geometry trajectory")
PYEOF

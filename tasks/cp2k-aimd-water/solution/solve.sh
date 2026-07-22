#!/usr/bin/env bash
# Oracle solution for cp2k-aimd-water.
set -euo pipefail
cd /workspace

cp /workspace/assets/h2o_aimd.inp ./h2o_aimd.inp

ln -sf /opt/cp2k/data/BASIS_MOLOPT ./BASIS_MOLOPT
ln -sf /opt/cp2k/data/GTH_POTENTIALS ./GTH_POTENTIALS

# The container is limited to 2 CPUs but sees all host cores; pin OMP threads
# to the quota so the psmp build does not oversubscribe and thrash.
export OMP_NUM_THREADS=2

mpirun -np 1 cp2k -i h2o_aimd.inp -o h2o_aimd.out

python3 << 'PYEOF'
import json

rows = []
with open("h2o_aimd-1.ener") as f:
    for line in f:
        if line.startswith("#"):
            continue
        p = line.split()
        # step, time[fs], Kin[au], Temp[K], Pot[au], Cons Qty[au], UsedTime[s]
        rows.append({
            "step": int(p[0]),
            "kin": float(p[2]),
            "temp": float(p[3]),
            "pot": float(p[4]),
            "cons": float(p[5]),
        })

if len(rows) != 21:
    raise RuntimeError(f"Expected 21 data rows in .ener, got {len(rows)}")

final_potential = rows[-1]["pot"]
mean_temperature = sum(r["temp"] for r in rows) / len(rows)
cons_qty_drift = abs(rows[-1]["cons"] - rows[0]["cons"])
n_md_steps = rows[-1]["step"]

results = {
    "values": {
        "final_potential": final_potential,
        "mean_temperature": mean_temperature,
        "cons_qty_drift": cons_qty_drift,
        "n_md_steps": n_md_steps,
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

print(f"E_pot(final)={final_potential:.9f} Ha, <T>={mean_temperature:.4f} K, "
      f"drift={cons_qty_drift:.3e} Ha, steps={n_md_steps}")
PYEOF

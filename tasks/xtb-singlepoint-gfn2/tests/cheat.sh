#!/usr/bin/env bash
# Informed cheat: a forger who knows xtb output format and the approximate
# GFN2 energetics of a small nitrile. Fabricates an xtb_sp.out — banner,
# fake SCC convergence marker, TOTAL ENERGY / HOMO-LUMO GAP summary lines,
# normal-termination footer — and a self-consistent results.json.
#
# Passes layers 0-3 (asset untouched, files exist, log well-formed,
# log<->results consistency).
# Must FAIL at layer 4/5: the guessed energy (4 decimals) is not the true
# deterministic xtb 6.7.1 value to 1e-6 Eh, and the verifier's real
# recompute on the pinned geometry returns the true energy — not the
# guess — breaking three-way agreement.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

fake_energy = -16.8432  # plausible GFN2 total energy guess for CH3CN
fake_gap = 13.85        # plausible HOMO-LUMO gap guess (eV)

out = f"""      -----------------------------------------------------------
     |                   =====================                   |
     |                           x T B                           |
     |                   =====================                   |
      -----------------------------------------------------------
   * xtb version 6.7.1 (edcfbbe) (fake banner)

   *** convergence criteria satisfied after 20 iterations ***

          | TOTAL ENERGY              {fake_energy:16.12f} Eh   |
          | HOMO-LUMO GAP             {fake_gap:16.12f} eV   |

normal termination of xtb
"""
with open("xtb_sp.out", "w") as f:
    f.write(out)

results = {
    "values": {
        "total_energy": fake_energy,
        "homo_lumo_gap": fake_gap,
    },
    "units": {
        "total_energy": "Eh",
        "homo_lumo_gap": "eV",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged xtb single-point output at {fake_energy} Eh")
PYEOF

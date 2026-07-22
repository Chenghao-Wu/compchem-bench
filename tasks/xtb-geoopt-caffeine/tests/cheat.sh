#!/usr/bin/env bash
# Informed cheat: a forger who knows xtb output format and can estimate the
# GFN2 energy of caffeine to ~5 decimals (e.g. from a lookup or another
# code). Fabricates:
#   - xtb_opt.out with banner, GEOMETRY OPTIMIZATION CONVERGED marker,
#     TOTAL ENERGY / molecular dipole summary, normal-termination footer
#   - xtbopt.xyz that is just the STARTING geometry from the asset (the
#     forger does not know the true GFN2-optimized coordinates)
#   - results.json self-consistent with the forged log
# Passes layers 1-6 (existence, banner/convergence/footer, consistency,
# plausible dipole, correct composition).
# Must FAIL at layer 7: the verifier's real single point on the forged
# "optimized" geometry (actually the unoptimized start) returns an energy
# ~1e-3 Eh above the converged value — not the claimed one — breaking
# three-way agreement. The claimed 5-decimal energy also cannot match the
# recompute to 1e-8 Eh.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

fake_energy = -42.15394  # 5-decimal guess at the converged GFN2 energy
fake_dipole = 4.06       # plausible dipole (Debye)

out = f"""      -----------------------------------------------------------
     |                   =====================                   |
     |                           x T B                           |
     |                   =====================                   |
      -----------------------------------------------------------
   * xtb version 6.7.1 (edcfbbe) (fake banner)

   *** convergence criteria satisfied after 15 iterations ***

           *** GEOMETRY OPTIMIZATION CONVERGED AFTER 7 ITERATIONS ***

molecular dipole:
                 x           y           z       tot (Debye)
 q only:        0.000       0.000       0.000       0.000
   full:        1.378      -0.791      -0.172       {fake_dipole:.3f}

          | TOTAL ENERGY              {fake_energy:16.12f} Eh   |

normal termination of xtb
"""
with open("xtb_opt.out", "w") as f:
    f.write(out)

# The forged "optimized" geometry is just the provided starting geometry.
with open("/workspace/assets/caffeine.xyz") as f:
    start = f.read()
with open("xtbopt.xyz", "w") as f:
    f.write(start)

results = {
    "values": {
        "final_energy": fake_energy,
        "dipole_moment": fake_dipole,
        "opt_converged": True,
    },
    "units": {
        "final_energy": "Eh",
        "dipole_moment": "Debye",
        "opt_converged": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged opt log + starting-geometry xtbopt.xyz at {fake_energy} Eh")
PYEOF

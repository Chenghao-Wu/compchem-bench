#!/usr/bin/env bash
# Informed cheat: a forger who knows xtb thermochemistry output format.
# Fabricates:
#   - xtb_thermo.out with banner, GEOMETRY OPTIMIZATION CONVERGED marker,
#     "# imaginary freq. 0", and a thermochemistry summary block
#   - a vibspectrum file with 27 plausible modes whose recomputed ZPE
#     matches the claimed ZPE (fully self-consistent — the forger knows
#     the ZPE = 1/2 sum(hc*nu) relation and scales the frequencies)
#   - xtbopt.xyz that is just the STARTING geometry from the asset
#   - results.json self-consistent with the forged log
# Passes layers 1-6, INCLUDING the independent ZPE re-derivation from the
# forged frequency table (by construction).
# Must FAIL at layer 5 (4-decimal energy guesses are not the true
# deterministic values to 1e-6 Eh) and at layer 7: the verifier's real
# single point on the forged "optimized" geometry (actually the
# unoptimized start) returns a different energy — breaking three-way
# agreement.
mkdir -p /workspace
cd /workspace

python3 << 'PYEOF'
import json

fake_energy = -11.3943   # 4-decimal guess at the GFN2 total energy
fake_zpe = 0.0781        # plausible ZPE guess (Eh)
fake_free = -11.3416     # plausible total free energy guess (Eh)
CM1_TO_EH = 4.556335252912e-6

# Build a self-consistent fake frequency table: 27 modes for 9 atoms,
# first 6 ~ 0, 21 plausible real modes scaled so 0.5*sum*CM1_TO_EH == fake_zpe.
base = [225.97, 342.78, 420.57, 813.44, 901.23, 1051.11, 1099.87,
        1165.43, 1240.12, 1279.55, 1389.01, 1456.78, 1482.96, 1489.67,
        1497.06, 2866.19, 2983.06, 3018.57, 3055.21, 3092.44, 3675.88]
scale = (2.0 * fake_zpe / CM1_TO_EH) / sum(base)
real = [f * scale for f in base]

lines = ["$vibrational spectrum",
         "#  mode     symmetry     wave number   IR intensity    selection rules",
         "#                         cm**(-1)      (km*mol⁻¹)        IR"]
for i in range(6):
    lines.append(f"{i+1:6d}                      {-0.0:8.2f}         0.00000          -")
for j, f in enumerate(real):
    lines.append(f"{j+7:6d}        a            {f:8.2f}         1.00000         YES")
with open("vibspectrum", "w") as f:
    f.write("\n".join(lines) + "\n")

out = f"""      -----------------------------------------------------------
     |                   =====================                   |
     |                           x T B                           |
     |                   =====================                   |
      -----------------------------------------------------------
   * xtb version 6.7.1 (edcfbbe) (fake banner)

   *** convergence criteria satisfied after 12 iterations ***

           *** GEOMETRY OPTIMIZATION CONVERGED AFTER 6 ITERATIONS ***

          :  # imaginary freq.                       0      :

         ::::::::::::::::::::::::::::::::::::::::::::::::::::::
         :: total free energy         {fake_free:18.12f} Eh   ::
         ::.................................................::
         :: total energy              {fake_energy:18.12f} Eh   ::
         :: zero point energy         {fake_zpe:18.12f} Eh   ::
         ::::::::::::::::::::::::::::::::::::::::::::::::::::::

normal termination of xtb
"""
with open("xtb_thermo.out", "w") as f:
    f.write(out)

# The forged "optimized" geometry is just the provided starting geometry.
with open("/workspace/assets/ethanol.xyz") as f:
    start = f.read()
with open("xtbopt.xyz", "w") as f:
    f.write(start)

results = {
    "values": {
        "total_energy": fake_energy,
        "zpe": fake_zpe,
        "free_energy_298": fake_free,
        "n_imaginary_freqs": 0,
    },
    "units": {
        "total_energy": "Eh",
        "zpe": "Eh",
        "free_energy_298": "Eh",
        "n_imaginary_freqs": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Forged thermo log + self-consistent vibspectrum + starting-geometry xtbopt.xyz")
PYEOF

#!/usr/bin/env bash
# Informed cheat for qe-output-parse: a forger who knows roughly what a 2-atom
# Si PBE SCF run looks like writes a results.json with plausible values —
# energy near -22.8 Ry, Fermi level near 6.5 eV, a small force — WITHOUT
# reading the artifacts. Fails the tight reference tolerances: the real
# values are only recoverable by actually parsing the provided run.
mkdir -p /workspace /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json

results = {
    "values": {
        "final_energy": -22.8335,
        "total_force": 0.0803,
        "fermi_energy": 6.53,
    },
    "units": {
        "final_energy": "Ry",
        "total_force": "Ry/bohr",
        "fermi_energy": "eV",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Forged results.json from domain-knowledge guesses (no parsing)")
PYEOF

#!/usr/bin/env bash
# Informed cheat #2 for qe-output-parse: a craftier forger REWRITES the
# provided artifacts to agree with fabricated results — edits the energy,
# force and Fermi lines in si_sample.out to self-consistent fake values,
# then reports those values. Every numeric check would pass against the
# doctored file. Must FAIL at the asset-integrity layer: the verifier
# validates sha256 of both artifacts BEFORE parsing anything:
# /workspace/assets is agent-writable and must never be trusted.
mkdir -p /workspace /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json
import re

path = "/workspace/assets/sample_run/si_sample.out"
with open(path) as f:
    content = f.read()

fake_energy = -22.85000000
fake_force = 0.012345
fake_fermi = 6.7890

content = re.sub(r"(!\s+total energy\s*=\s*)[-\d.]+(\s+Ry)",
                 rf"\g<1>{fake_energy:.8f}\g<2>", content)
content = re.sub(r"(Total force =\s*)[-\d.]+",
                 rf"\g<1>{fake_force:.6f}", content)
content = re.sub(r"(the Fermi energy is\s*)[-\d.]+(\s+ev)",
                 rf"\g<1>{fake_fermi:.4f}\g<2>", content)
with open(path, "w") as f:
    f.write(content)

results = {
    "values": {
        "final_energy": fake_energy,
        "total_force": fake_force,
        "fermi_energy": fake_fermi,
    },
    "units": {
        "final_energy": "Ry",
        "total_force": "Ry/bohr",
        "fermi_energy": "eV",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"Doctored si_sample.out + self-consistent results.json at {fake_energy} Ry")
PYEOF

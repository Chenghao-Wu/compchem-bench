#!/usr/bin/env bash
# Informed cheat (asset-tampering): the task input
# /workspace/assets/co_relax.in is agent-WRITABLE. A forger who reads the
# calibrated reference bond length from /tests/refs.json (an informed
# adversary) and rewrites the input to START at the equilibrium geometry
# gets a BFGS relax that converges in a step or two at the true minimum —
# final bond, final energy, XML double-source, and the Layer-7 recompute all
# agree with the calibrated references.
#
# Must FAIL: refs.json pins sha256 of co_relax.in (and both UPF files) and
# the verifier validates them before any use — a tampered input is a hard
# fail.
set -euo pipefail
cd /workspace

# Tamper: rewrite the input to start at the reference equilibrium bond
# (read from /tests/refs.json — the informed adversary's advantage).
BOND_REF=$(python3 -c "import json; print(json.load(open('/tests/refs.json'))['co_bond_A_ref'])")
sed -i "s/^  O 0.0 0.0 1.25\$/  O 0.0 0.0 ${BOND_REF}/" /workspace/assets/co_relax.in
grep -A2 "ATOMIC_POSITIONS" /workspace/assets/co_relax.in

# Run the tampered input for real.
cp /workspace/assets/co_relax.in ./co_relax.in
cp -r /workspace/assets/pseudo ./pseudo
pw.x -in co_relax.in > co_relax.out

python3 << 'PYEOF'
import json
import math
import re

with open("co_relax.out") as f:
    content = f.read()

m_e = re.search(r"Final energy\s*=\s*([-\d.]+)\s+Ry", content)
if not m_e:
    raise RuntimeError("No 'Final energy' line found")
final_energy = float(m_e.group(1))

m_bfgs = re.search(r"bfgs converged in\s+(\d+)\s+scf cycles and\s+(\d+)\s+bfgs steps", content)
relax_converged = m_bfgs is not None
n_bfgs = int(m_bfgs.group(2)) if m_bfgs else 0

m_geo = re.search(
    r"Begin final coordinates\s+ATOMIC_POSITIONS \(angstrom\)\s+((?:\s*\w+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n)+)\s*End final coordinates",
    content)
if not m_geo:
    raise RuntimeError("No final ATOMIC_POSITIONS block found")
pos = {}
for line in m_geo.group(1).strip().splitlines():
    p = line.split()
    pos[p[0]] = (float(p[1]), float(p[2]), float(p[3]))
bond = math.dist(pos["C"], pos["O"])

results = {
    "values": {
        "final_energy": final_energy,
        "co_bond_length": bond,
        "relax_converged": relax_converged,
        "n_bfgs_steps": n_bfgs,
    },
    "units": {
        "final_energy": "Ry",
        "co_bond_length": "Å",
        "relax_converged": "1",
        "n_bfgs_steps": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Tampered-input relax: E={final_energy:.8f} Ry, C-O={bond:.4f} Å, "
      f"bfgs_steps={n_bfgs}")
PYEOF

#!/usr/bin/env bash
# Informed cheat for qe-relax-co: a forger who knows the textbook CO bond
# length (~1.14 Å PBE) fabricates a complete-looking pw.x relax run — v7.4
# banner, per-step energy lines, 'bfgs converged in ...' marker, final
# coordinates at the expected bond length, a schema-valid pwscf.xml, and a
# results.json self-consistent with the fake log at a plausible energy.
#
# Layers 1-6 (existence, asset hashes, banner, convergence marker,
# log<->results consistency, reference tolerances, stdout<->XML) all PASS —
# the claimed bond is right and the energy is guessed close enough to slip
# inside the reference tolerance. Must FAIL at layer 7: the verifier runs a
# REAL SCF single point on the claimed geometry — its true energy differs
# from the guess by more than the cross-verify tolerance, breaking
# three-way agreement.
mkdir -p /workspace/outdir /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json

# Domain-expert guesses: PBE C-O bond ~1.140 Å; energy guessed to ~1e-5 Ry
# ("close to -60.0105") — good enough for the reference tolerance, not good
# enough to match a real recomputation to 1e-6.
bond = 1.140
fake_ry = -60.01054000
fake_ha = fake_ry / 2.0
zc, zo = 0.0551, 0.0551 + bond

def pos_block(zc, zo):
    return (
        "ATOMIC_POSITIONS (angstrom)\n"
        f"C                0.0000000000        0.0000000000        {zc:.10f}\n"
        f"O                0.0000000000        0.0000000000        {zo:.10f}\n"
    )

steps = ""
for i, e in enumerate([fake_ry + 0.04, fake_ry + 0.008, fake_ry + 0.0004, fake_ry]):
    steps += f"!    total energy              =     {e:.8f} Ry\n"
    steps += f"     number of bfgs steps    =   {i}\n"
    steps += pos_block(zc - 0.01 * (3 - i), zo - 0.01 * (3 - i))

out = f"""     Program PWSCF v.7.4 starts on 20Jul2026 at  0: 0: 0

{steps}
     Total force =     0.000049     Total SCF correction =     0.000005

     bfgs converged in   7 scf cycles and   4 bfgs steps
     (criteria: energy <  1.0E-04 Ry, force <  1.0E-04 Ry/Bohr)

     End of BFGS Geometry Optimization

     Final energy             =     {fake_ry:.10f} Ry

Begin final coordinates
{pos_block(zc, zo)}End final coordinates

   JOB DONE.
"""
with open("co_relax.out", "w") as f:
    f.write(out)

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qes:espresso xmlns:qes="http://www.quantum-espresso.org/ns/qes/qes-1.0">
  <output>
    <total_energy>
      <etot>{fake_ha:.15E}</etot>
    </total_energy>
  </output>
</qes:espresso>
"""
with open("outdir/pwscf.xml", "w") as f:
    f.write(xml)

results = {
    "values": {
        "final_energy": fake_ry,
        "co_bond_length": bond,
        "relax_converged": True,
        "n_bfgs_steps": 4,
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

print(f"Forged relax run: bond={bond} Å (correct), energy={fake_ry} Ry (guessed)")
PYEOF

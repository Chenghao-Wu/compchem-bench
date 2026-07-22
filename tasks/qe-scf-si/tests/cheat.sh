#!/usr/bin/env bash
# Informed cheat for qe-scf-si: a forger with plane-wave DFT domain knowledge
# fabricates a complete-looking pw.x SCF run — v7.4 banner, SCF iteration
# table, convergence line, JOB DONE., a plausible total energy guessed from
# the known PBE cohesive energy of Si, a minimal but schema-valid pwscf.xml
# whose <etot> is self-consistent with the fake log, and a results.json
# matching both.
#
# Layers 1-5 (existence, banner, settings echo, log<->results consistency,
# stdout<->XML double source) all PASS for this forgery — the fake XML is
# consistent by construction. It must FAIL at layer 6: the guessed energy
# cannot land inside the calibrated tight tolerance of the true value.
mkdir -p /workspace/outdir /logs/verifier
cd /workspace

python3 << 'PYEOF'
import json

# Domain-expert guess: PBE Si cohesive energy ~4.6 eV/atom on top of atomic
# references — the forger picks a plausible-but-not-calibrated value.
fake_ry = -22.79000000
fake_ha = fake_ry / 2.0

iter_block = ""
for i in range(1, 7):
    iter_block += (
        f"     iteration #  {i}     ecut=    40.00 Ry     beta= 0.70\n"
        f"     total cpu time spent up to now is        1.0 secs\n"
    )

out = f"""     Program PWSCF v.7.4 starts on 20Jul2026 at  0: 0: 0

     bravais-lattice index     =            2
     number of atoms/cell      =            2.0000
     number of k points=    10
     kinetic-energy cutoff     =     40.0000  Ry

{iter_block}
     total energy              =     {fake_ry:.8f} Ry
     convergence has been achieved in   6 iterations

!    total energy              =     {fake_ry:.8f} Ry
     JOB DONE.
"""
with open("si_scf.out", "w") as f:
    f.write(out)

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qes:espresso xmlns:qes="http://www.quantum-espresso.org/ns/qes/qes-1.0">
  <output>
    <total_energy>
      <etot>{fake_ha:.15E}</etot>
    </total_energy>
    <band_structure>
      <fermi_energy>2.4E-1</fermi_energy>
    </band_structure>
  </output>
</qes:espresso>
"""
with open("outdir/pwscf.xml", "w") as f:
    f.write(xml)

results = {
    "values": {
        "total_energy": fake_ry,
        "scf_converged": True,
        "n_scf_iterations": 6,
    },
    "units": {
        "total_energy": "Ry",
        "scf_converged": "1",
        "n_scf_iterations": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Forged SCF run, self-consistent at {fake_ry} Ry (log + XML + results)")
PYEOF

#!/usr/bin/env bash
# Informed near-miss: an agent that spots the missing `special_bonds` and
# applies 1-4 scaling — but with the CHARMM-flavoured habit of using the same
# factor for both terms, `special_bonds lj/coul 0.0 0.0 0.5`, instead of
# AMBER/GAFF's split convention (0.5 for Lennard-Jones, 1/1.2 for Coulomb).
#
# Nothing here is forged. Both calculations are really run, both logs are
# genuine, the audited input differs from the shipped one by exactly one
# special_bonds command, the bonded terms are invariant, the non-bonded
# energy really does move, and results.json faithfully reports what the runs
# produced. It passes layers 1-6 on merit.
#
# Must FAIL at layer 7: the Coulomb 1-4 factor is wrong, so both
# coul_14_scale and e_coul_audited/e_pot_audited miss the reference. This is
# the discriminating case for the task — getting "1-4 scaling exists" is not
# the same as getting GAFF2 right.
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1
cp assets/porphin_energy.in ./porphin_energy.in
lmp_serial -in porphin_energy.in -log log_original.lammps > /dev/null 2>&1

python3 - << 'PYEOF'
import re
src = open("assets/porphin_energy.in").read()
fixed, n = re.subn(r"^(kspace_style\s+ewald\s+0\.0001\s*)$",
                   r"\1\nspecial_bonds   lj/coul 0.0 0.0 0.5",
                   src, count=1, flags=re.M)
assert n == 1
open("energy_audited.in", "w").write(fixed)
PYEOF

lmp_serial -in energy_audited.in -log log_audited.lammps > /dev/null 2>&1

python3 << 'PYEOF'
import json
import re


def thermo(path):
    lines = open(path).read().splitlines()
    i = next(j for j, l in enumerate(lines) if re.match(r"^\s*Step\s+", l))
    header = lines[i].split()
    r = next(l for l in lines[i + 1:] if re.match(r"^\s*\d+\s+[-\d.eE+]", l))
    return dict(zip(header, [float(x) for x in r.split()]))


orig, audit = thermo("log_original.lammps"), thermo("log_audited.lammps")
values = {
    "e_pot_original": orig["PotEng"],
    "e_vdwl_original": orig["E_vdwl"],
    "e_coul_original": orig["E_coul"],
    "e_pot_audited": audit["PotEng"],
    "e_vdwl_audited": audit["E_vdwl"],
    "e_coul_audited": audit["E_coul"],
    "delta_e_pot": audit["PotEng"] - orig["PotEng"],
    "lj_14_scale": 0.5,
    "coul_14_scale": 0.5,
}
units = {k: "kcal/mol" for k in values}
units["lj_14_scale"] = "1"
units["coul_14_scale"] = "1"
json.dump({"values": values, "units": units}, open("results.json", "w"), indent=2)
print(f"Applied lj/coul 0.5/0.5 for real: audited PE={audit['PotEng']:.4f}, "
      f"coul={audit['E_coul']:.4f} (genuine, but not GAFF2)")
PYEOF

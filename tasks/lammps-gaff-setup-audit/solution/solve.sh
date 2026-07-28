#!/usr/bin/env bash
# Oracle solution for lammps-gaff-setup-audit.
#
# The defect: the script never issues `special_bonds`. LAMMPS therefore uses
# its default, `lj/coul 0.0 0.0 0.0`, which excludes 1-2, 1-3 AND 1-4 pairs
# outright. GAFF2 inherits AMBER's convention that 1-4 pairs are retained at
# reduced weight — 0.5 for Lennard-Jones, 1/1.2 for Coulomb — so with the
# default the 1-4 contributions are simply missing and the reported energy
# belongs to no parameterised force field.
#
# The fix is one line, `special_bonds amber`. It leaves every bonded term
# untouched and moves only evdwl and ecoul.
set -euo pipefail
cd /workspace

cp assets/porphin_energy.in ./porphin_energy.in

export OMP_NUM_THREADS=1
lmp_serial -in porphin_energy.in -log log_original.lammps

# Insert the missing convention directly after the pair/kspace declarations,
# before the coefficients are included.
python3 - << 'PYEOF'
import re

src = open("assets/porphin_energy.in").read()
fixed, n = re.subn(r"^(kspace_style\s+ewald\s+0\.0001\s*)$",
                   r"\1\nspecial_bonds   amber",
                   src, count=1, flags=re.MULTILINE)
if n != 1:
    raise SystemExit("could not locate the kspace_style line to patch")
open("energy_audited.in", "w").write(fixed)
PYEOF

lmp_serial -in energy_audited.in -log log_audited.lammps

python3 << 'PYEOF'
import json
import re


def thermo(log_path):
    """{thermo keyword: value} from the single run-0 table in a log."""
    lines = open(log_path).read().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*Step\s+", line):
            header = line.split()
            for nxt in lines[i + 1:]:
                if re.match(r"^\s*\d+\s+[-\d.eE+]", nxt):
                    return dict(zip(header, [float(x) for x in nxt.split()]))
    raise SystemExit(f"no thermo table in {log_path}")


orig = thermo("log_original.lammps")
audit = thermo("log_audited.lammps")

values = {
    "e_pot_original": orig["PotEng"],
    "e_vdwl_original": orig["E_vdwl"],
    "e_coul_original": orig["E_coul"],
    "e_pot_audited": audit["PotEng"],
    "e_vdwl_audited": audit["E_vdwl"],
    "e_coul_audited": audit["E_coul"],
    "delta_e_pot": audit["PotEng"] - orig["PotEng"],
    # AMBER/GAFF 1-4 conventions, as applied by `special_bonds amber`.
    "lj_14_scale": 0.5,
    "coul_14_scale": 1.0 / 1.2,
}
units = {k: "kcal/mol" for k in values}
units["lj_14_scale"] = "1"
units["coul_14_scale"] = "1"

with open("results.json", "w") as f:
    json.dump({"values": values, "units": units}, f, indent=2)

print(f"as shipped : PE={values['e_pot_original']:.5f}  "
      f"vdwl={values['e_vdwl_original']:.5f}  "
      f"coul={values['e_coul_original']:.5f}")
print(f"audited    : PE={values['e_pot_audited']:.5f}  "
      f"vdwl={values['e_vdwl_audited']:.5f}  "
      f"coul={values['e_coul_audited']:.5f}")
print(f"delta PE   : {values['delta_e_pot']:+.5f} kcal/mol")
PYEOF

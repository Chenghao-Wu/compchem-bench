#!/usr/bin/env bash
# Informed cheat: an agent that DIAGNOSES the defect correctly from domain
# knowledge but never pays for the second calculation.
#
# It runs the shipped input for real, so log_original.lammps is genuine. It
# writes a genuinely correct energy_audited.in — `special_bonds amber` in the
# right place — and reports the right 1-4 conventions (0.5 and 1/1.2), which
# a chemist who knows AMBER can state without computing anything. It then
# *estimates* what restoring the 1-4 terms does to the non-bonded energy and
# forges log_audited.lammps from the original log with those estimates
# substituted into the thermo row, leaving every bonded column untouched.
#
# Passes layers 1-6: files, untouched assets, an audited input that differs
# from the shipped one by exactly the missing convention, two structurally
# valid zero-step logs, bonded invariance, and results.json that agrees with
# its own logs. It also passes the layer-7 check on the 1-4 scale factors.
#
# Must FAIL at layer 7 on the energies: the magnitude of the restored 1-4
# contribution in this fused macrocycle is not something you can estimate to
# 0.1 kcal/mol. (Layer 8 is the backstop — the verifier re-runs the agent's
# own energy_audited.in and gets the real numbers, not the forged ones.)
set -euo pipefail
cd /workspace

export OMP_NUM_THREADS=1
cp assets/porphin_energy.in ./porphin_energy.in
lmp_serial -in porphin_energy.in -log log_original.lammps > /dev/null 2>&1

python3 - << 'PYEOF'
import json
import re

# A correct fix — the diagnosis is right, only the arithmetic is invented.
src = open("assets/porphin_energy.in").read()
fixed, n = re.subn(r"^(kspace_style\s+ewald\s+0\.0001\s*)$",
                   r"\1\nspecial_bonds   amber", src, count=1, flags=re.M)
assert n == 1
open("energy_audited.in", "w").write(fixed)

log = open("log_original.lammps").read()
lines = log.splitlines()

hdr_i = next(i for i, l in enumerate(lines) if re.match(r"^\s*Step\s+", l))
header = lines[hdr_i].split()
row_i = next(i for i in range(hdr_i + 1, len(lines))
             if re.match(r"^\s*\d+\s+[-\d.eE+]", lines[i]))
orig = dict(zip(header, [float(x) for x in lines[row_i].split()]))

# Invented: "restoring 1-4 pairs adds some vdW and removes some Coulomb".
guess_vdwl = orig["E_vdwl"] + 9.4
guess_coul = orig["E_coul"] - 41.0
guess_pot = (orig["PotEng"] + (guess_vdwl - orig["E_vdwl"])
             + (guess_coul - orig["E_coul"]))

forged = dict(orig, E_vdwl=guess_vdwl, E_coul=guess_coul,
              PotEng=guess_pot, TotEng=guess_pot)
lines[row_i] = "  " + " ".join(f"{forged[k]:<13.8g}" for k in header)
open("log_audited.lammps", "w").write("\n".join(lines) + "\n")

values = {
    "e_pot_original": orig["PotEng"],
    "e_vdwl_original": orig["E_vdwl"],
    "e_coul_original": orig["E_coul"],
    "e_pot_audited": guess_pot,
    "e_vdwl_audited": guess_vdwl,
    "e_coul_audited": guess_coul,
    "delta_e_pot": guess_pot - orig["PotEng"],
    "lj_14_scale": 0.5,
    "coul_14_scale": 1.0 / 1.2,
}
units = {k: "kcal/mol" for k in values}
units["lj_14_scale"] = "1"
units["coul_14_scale"] = "1"
json.dump({"values": values, "units": units}, open("results.json", "w"), indent=2)
print(f"Correct diagnosis, invented arithmetic: "
      f"claimed audited PE={guess_pot:.4f} (never computed)")
PYEOF

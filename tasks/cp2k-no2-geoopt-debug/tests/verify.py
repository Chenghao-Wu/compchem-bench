#!/usr/bin/env python3
"""
Verifier for cp2k-no2-geoopt-debug:
  1. File existence + results.json schema (values/units)
  2. final.inp repair checks (spin-polarized fix present; physics-preserving
     settings kept; no charge/ignore-convergence shortcuts)
  3. Output integrity (CP2K banner, SCF converged, GEO_OPT completed,
     normal termination, no non-converged SCF anywhere)
  4. log <-> results consistency (last ENERGY| line)
  5. Numerical tolerance vs calibrated refs
"""
import json
import sys
import os
import re

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

ENERGY_RE = re.compile(r"ENERGY\|.*?Total FORCE_EVAL.*?:\s*([-\d.E+]+)")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def last_energy(log_content):
    matches = ENERGY_RE.findall(log_content)
    if not matches:
        fail("No 'ENERGY| Total FORCE_EVAL' line found in CP2K output")
    return float(matches[-1])


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("final.inp", "no2_geoopt.out", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "geoopt_converged"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: final.inp repair checks ───────────────────────────────────────────
with open(os.path.join(WORKSPACE, "final.inp")) as f:
    fixed = f.read()

# Strip comment lines so commented-out keywords cannot game the token checks.
code = "\n".join(line.split("!")[0] for line in fixed.splitlines())

def _uks_enabled(code: str) -> bool:
    """True if UKS/LSD is enabled, accepting CP2K's logical-keyword idioms.

    CP2K logical keywords mean TRUE when given without a value (bare `LSD`),
    and also accept `LSD TRUE`, `LSD = .TRUE.`, `LSD ON`, etc. Parse per line
    (comments are already stripped) so a value on the next line cannot be
    misread as the keyword's value; explicit-false forms do not count.
    """
    for line in code.splitlines():
        line = line.split("!")[0].split("#")[0]  # CP2K comments: ! and #
        m = re.search(r"(?<![&\w])(UKS|LSD)\b[ \t]*=?[ \t]*(\.?[A-Za-z0-9]+\.?)?",
                      line, re.IGNORECASE)
        if not m or "&" in line[: m.start()]:
            continue  # absent on this line, or part of an (&END) section token
        val = (m.group(2) or "").strip(".").upper()
        if val in ("", "TRUE", "T", "YES", "ON", "1"):
            return True
    return False


check(_uks_enabled(code),
      "final.inp does not enable a spin-polarized (UKS/LSD) calculation")
check(re.search(r"\bMULTIPLICITY\s+2\b", code),
      "final.inp does not set MULTIPLICITY 2 (NO2 ground state is a doublet)")
check(not re.search(r"\bCHARGE\b", code),
      "final.inp sets CHARGE: charging NO2 to force a closed shell changes the system")
check(not re.search(r"\bIGNORE_CONVERGENCE_FAILURE\b", code),
      "final.inp sets IGNORE_CONVERGENCE_FAILURE: the SCF must actually converge")

# Intended physics/settings must be kept.
check(re.search(r"&XC_FUNCTIONAL\s+PBE", code), "final.inp must keep the PBE functional")
kind_n = re.search(r"&KIND\s+N\b(.*?)&END\s+KIND", code, re.IGNORECASE | re.DOTALL)
kind_o = re.search(r"&KIND\s+O\b(.*?)&END\s+KIND", code, re.IGNORECASE | re.DOTALL)
check(kind_n and "DZVP-MOLOPT-GTH" in kind_n.group(1) and "GTH-PBE-q5" in kind_n.group(1),
      "final.inp must assign N the DZVP-MOLOPT-GTH basis and GTH-PBE-q5 pseudopotential")
check(kind_o and "DZVP-MOLOPT-GTH" in kind_o.group(1) and "GTH-PBE-q6" in kind_o.group(1),
      "final.inp must assign O the DZVP-MOLOPT-GTH basis and GTH-PBE-q6 pseudopotential")
check(not re.search(r"CUTOFF\s*\[", code),
      "final.inp must keep CUTOFF in default Hartree units (no unit bracket)")
check(re.search(r"CUTOFF\s+400", code), "final.inp must keep CUTOFF 400")
check(re.search(r"REL_CUTOFF\s+50", code), "final.inp must keep REL_CUTOFF 50")
check(re.search(r"RUN_TYPE\s+GEO_OPT", code), "final.inp must keep RUN_TYPE GEO_OPT")

# ── Layer 3: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "no2_geoopt.out")) as f:
    content = f.read()

check("CP2K" in content, "no2_geoopt.out missing CP2K banner")
check("SCF run converged" in content, "no2_geoopt.out: SCF did not converge")
check("SCF run NOT converged" not in content,
      "no2_geoopt.out contains a non-converged SCF run")
check("GEOMETRY OPTIMIZATION COMPLETED" in content,
      "no2_geoopt.out: geometry optimization did not complete")
check("PROGRAM ENDED AT" in content,
      "no2_geoopt.out missing normal-termination footer 'PROGRAM ENDED AT'")
check(values["geoopt_converged"] is True, "geoopt_converged must be true")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
energy_log = last_energy(content)
energy_rep = values["total_energy"]

check(
    abs(energy_log - energy_rep) <= refs["consistency_energy_tol_Ha"],
    f"results.json energy {energy_rep:.10f} Ha != log energy {energy_log:.10f} Ha "
    f"(tol {refs['consistency_energy_tol_Ha']:.1e})",
)

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
energy_ref = refs["total_energy_Ha_ref"]
energy_tol = refs["total_energy_Ha_tol"]
check(
    abs(energy_rep - energy_ref) <= energy_tol,
    f"total_energy={energy_rep:.8f} Ha differs from ref {energy_ref:.8f} Ha by >{energy_tol:.2e}",
)

print("PASS: cp2k-no2-geoopt-debug")

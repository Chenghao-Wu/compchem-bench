#!/usr/bin/env python3
"""
Verifier for lammps-gaff-setup-audit:
  1. File existence + results.json schema (values/units)
  2. Asset integrity: every asset the verifier consumes is pinned by sha256
  3. Audited-input integrity: the corrected script differs from the shipped
     one by exactly the added non-bonded convention (plus, optionally, a
     richer thermo_style) — nothing else about the physics may move
  4. Log integrity: both logs carry the banner, the completion footer, no
     ERROR line, and a genuine zero-step run on 40 atoms
  5. Bonded invariance: ebond/eangle/edihed/eimp identical across the two
     runs — the correction must complete the force field, not change it
  6. Consistency: results.json matches the agent's own two logs
  7. Numerical tolerance: every energy within tolerance of the reference,
     and the reported 1-4 scale factors match the AMBER/GAFF convention
  8. REAL RECOMPUTE: the in-image LAMMPS re-runs both the shipped and the
     corrected single point and must reproduce every reported energy.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets")
REFS_PATH = "/tests/refs.json"

# A LAMMPS-formatted floating point number, incl. signed exponents.
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

N_ATOMS = 40
AUDITED_IN = "energy_audited.in"
LOG_ORIGINAL = "log_original.lammps"
LOG_AUDITED = "log_audited.lammps"

BONDED_KEYS = ("E_bond", "E_angle", "E_dihed", "E_impro")
ENERGY_KEYS = ("e_pot_original", "e_vdwl_original", "e_coul_original",
               "e_pot_audited", "e_vdwl_audited", "e_coul_audited",
               "delta_e_pot")
SCALE_KEYS = ("lj_14_scale", "coul_14_scale")

# thermo keyword -> the results.json suffix it feeds
THERMO_OF = {"e_pot": "PotEng", "e_vdwl": "E_vdwl", "e_coul": "E_coul"}


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def thermo_row(text, source):
    """{thermo keyword: float} from the first thermo table in `text`."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*Step\s+", line):
            header = line.split()
            for nxt in lines[i + 1:]:
                if re.match(r"^\s*\d+\s+[-\d.eE+]", nxt):
                    row = nxt.split()
                    check(len(header) == len(row),
                          f"{source}: thermo header has {len(header)} columns "
                          f"but the data row has {len(row)}")
                    return dict(zip(header, [float(x) for x in row]))
    fail(f"{source}: could not locate a thermo table with a data row")


def commands(text):
    """Normalised command list: comments, blank lines and spacing removed."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        line = " ".join(line.split())
        if line:
            out.append(line)
    return out


def check_log(text, name):
    check("LAMMPS" in text, f"{name} missing LAMMPS banner")
    check("Total wall time" in text,
          f"{name} missing 'Total wall time' — run incomplete")
    check(not re.search(r"^ERROR", text, re.MULTILINE),
          f"{name} contains an ERROR line — the run did not complete cleanly")
    loop = re.search(r"Loop time of \S+ on \d+ procs for (\d+) steps with "
                     r"(\d+) atoms", text)
    check(loop is not None, f"{name} has no 'Loop time' line — nothing was run")
    check(int(loop.group(1)) == 0,
          f"{name} records a {loop.group(1)}-step run; this task is a "
          f"single-point evaluation (run 0)")
    check(int(loop.group(2)) == N_ATOMS,
          f"{name} run has {loop.group(2)} atoms (expected {N_ATOMS})")


with open(REFS_PATH) as f:
    refs = json.load(f)

LMP = shutil.which("lmp_serial") or "/usr/bin/lmp_serial"
check(os.path.isfile(LMP), "lmp_serial not found in the image — cannot recompute")

# ── Layer 1: File existence + schema ──────────────────────────────────────────
for fname in (AUDITED_IN, LOG_ORIGINAL, LOG_AUDITED, "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    try:
        results = json.load(f)
    except Exception as e:
        fail(f"results.json is not valid JSON: {e}")

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ENERGY_KEYS + SCALE_KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
    try:
        values[key] = float(values[key])
    except Exception:
        fail(f"results.json values[{key!r}] is not a number: {values[key]!r}")

# ── Layer 2: Asset integrity ──────────────────────────────────────────────────
for rel, expected in refs["asset_hashes"].items():
    path = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(path), f"Pinned asset missing from the workspace: {rel}")
    actual = sha256_file(path)
    check(actual == expected,
          f"Asset {rel} was modified: {actual} != pinned {expected}")

# ── Layer 3: Audited-input integrity ──────────────────────────────────────────
with open(os.path.join(ASSETS, "porphin_energy.in")) as f:
    original_cmds = commands(f.read())
with open(os.path.join(WORKSPACE, AUDITED_IN)) as f:
    audited_src = f.read()
audited_cmds = commands(audited_src)

special = [c for c in audited_cmds if c.lower().startswith("special_bonds")]
check(len(special) == 1,
      f"{AUDITED_IN} contains {len(special)} 'special_bonds' commands; the "
      f"correction is a single missing non-bonded convention")

# Strip the added convention and neutralise thermo_style (the instruction
# permits a richer thermo line); what remains must be the shipped script.
def canonical(cmds):
    out = []
    for c in cmds:
        if c.lower().startswith("special_bonds"):
            continue
        if c.lower().startswith("thermo_style"):
            c = "thermo_style <any>"
        out.append(c)
    return out


check(canonical(audited_cmds) == canonical(original_cmds),
      f"{AUDITED_IN} differs from the shipped input by more than the one "
      f"missing setting. Only that setting (and optionally a richer "
      f"thermo_style) may change.\n"
      f"  shipped: {canonical(original_cmds)}\n"
      f"  audited: {canonical(audited_cmds)}")

check(any(c.lower().startswith("read_data") and "assets/system_gaff2.data" in c
          for c in audited_cmds),
      f"{AUDITED_IN} must still read 'assets/system_gaff2.data'")

# ── Layer 4: Log integrity ────────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, LOG_ORIGINAL)) as f:
    log_orig_text = f.read()
with open(os.path.join(WORKSPACE, LOG_AUDITED)) as f:
    log_audit_text = f.read()

check_log(log_orig_text, LOG_ORIGINAL)
check_log(log_audit_text, LOG_AUDITED)

orig_thermo = thermo_row(log_orig_text, LOG_ORIGINAL)
audit_thermo = thermo_row(log_audit_text, LOG_AUDITED)

for name, row in ((LOG_ORIGINAL, orig_thermo), (LOG_AUDITED, audit_thermo)):
    missing = [k for k in ("PotEng", "E_vdwl", "E_coul") + BONDED_KEYS
               if k not in row]
    check(not missing,
          f"{name}: thermo output is missing the column(s) {missing} — keep "
          f"the thermo output at least as detailed as the original's")

# ── Layer 5: Bonded invariance ────────────────────────────────────────────────
bonded_tol = refs["bonded_invariance_tol"]
for key in BONDED_KEYS:
    check(abs(orig_thermo[key] - audit_thermo[key]) <= bonded_tol,
          f"bonded term {key} changed between your two runs "
          f"({orig_thermo[key]:.8g} -> {audit_thermo[key]:.8g}). The missing "
          f"setting affects only the non-bonded terms; a correction that "
          f"moves the bonded energy has changed the physics")

check(abs(audit_thermo["E_vdwl"] - orig_thermo["E_vdwl"]) > refs["min_nonbonded_shift"],
      "the non-bonded energy is essentially unchanged between your two runs — "
      "the corrected input does not actually apply the missing convention")

# ── Layer 6: Consistency with the agent's own logs ────────────────────────────
cons_tol = refs["consistency_tol"]
for suffix, row, name in (("original", orig_thermo, LOG_ORIGINAL),
                          ("audited", audit_thermo, LOG_AUDITED)):
    for stem, thermo_key in THERMO_OF.items():
        key = f"{stem}_{suffix}"
        check(abs(values[key] - row[thermo_key]) <= cons_tol,
              f"results.json {key}={values[key]:.6f} does not match "
              f"{thermo_key} in your own {name} ({row[thermo_key]:.6f}, "
              f"tol {cons_tol})")

expected_delta = values["e_pot_audited"] - values["e_pot_original"]
check(abs(values["delta_e_pot"] - expected_delta) <= refs["closure_tol"],
      f"delta_e_pot={values['delta_e_pot']:.6f} != e_pot_audited - "
      f"e_pot_original = {expected_delta:.6f}")

# ── Layer 7: Numerical tolerance + the 1-4 convention ─────────────────────────
energy_tol = refs["energy_tol"]
for key in ENERGY_KEYS:
    ref = refs["energy_ref"][key]
    check(abs(values[key] - ref) <= energy_tol,
          f"{key}={values[key]:.6f} differs from the reference {ref:.6f} by "
          f"more than {energy_tol} kcal/mol")

scale_tol = refs["scale_tol"]
for key in SCALE_KEYS:
    ref = refs["scale_ref"][key]
    check(abs(values[key] - ref) <= scale_tol,
          f"{key}={values[key]:.6f} is not the GAFF2/AMBER 1-4 convention "
          f"(expected {ref:.6f} +/- {scale_tol})")

# ── Layer 8: REAL RECOMPUTE of both single points ─────────────────────────────
env = dict(os.environ, OMP_NUM_THREADS="1")


def recompute(input_path, tag):
    """Run a single point from `input_path` with assets resolvable, return thermo."""
    tmp = tempfile.mkdtemp(prefix=f"verify_{tag}_")
    os.symlink(ASSETS, os.path.join(tmp, "assets"))
    dst = os.path.join(tmp, "run.in")
    shutil.copy(input_path, dst)
    proc = subprocess.run([LMP, "-in", "run.in", "-log", "none"], cwd=tmp,
                          env=env, capture_output=True, text=True, timeout=300)
    check(proc.returncode == 0,
          f"verifier recompute of the {tag} single point failed "
          f"(exit {proc.returncode}):\n{proc.stdout[-2000:]}\n"
          f"{proc.stderr[-2000:]}")
    row = thermo_row(proc.stdout, f"verifier {tag} recompute")
    shutil.rmtree(tmp, ignore_errors=True)
    return row


rc_orig = recompute(os.path.join(ASSETS, "porphin_energy.in"), "shipped")
rc_audit = recompute(os.path.join(WORKSPACE, AUDITED_IN), "audited")

rc_tol = refs["recompute_tol"]
for suffix, row in (("original", rc_orig), ("audited", rc_audit)):
    for stem, thermo_key in THERMO_OF.items():
        key = f"{stem}_{suffix}"
        check(abs(values[key] - row[thermo_key]) <= rc_tol,
              f"RECOMPUTE: you reported {key}={values[key]:.6f}, but the "
              f"verifier's independent {suffix} single point gives "
              f"{row[thermo_key]:.6f} (tol {rc_tol}) — the reported energy is "
              f"not backed by the calculation")

print("PASS: lammps-gaff-setup-audit")

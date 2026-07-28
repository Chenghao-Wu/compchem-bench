#!/usr/bin/env python3
"""
Verifier for lammps-minimize-var-bug:
  1. File existence + results.json schema (values/units)
  2. Asset integrity: every asset the verifier consumes is pinned by sha256
  3. Fixed-input integrity: the physics is unchanged (same styles, same
     min_style/minimize line, same relative asset paths) and the three
     summary lines are still emitted
  4. Log integrity: banner, footer, no ERROR, a genuine minimisation on 40
     atoms, and summary lines that agree with results.json
  5. Numerical tolerance: energies and iteration count vs the reference,
     plus internal closure delta_e == e_final - e_initial
  6. REAL RECOMPUTE: the in-image LAMMPS re-evaluates the potential energy
     of the agent's porphin_minimized.data — it must equal e_final, i.e.
     the written structure really is the minimised one
  7. GENERALISATION PROBE: the agent's own fixed input is re-run against a
     deterministically perturbed copy of the molecule, whose true energies
     the verifier computes independently. A script that prints hardcoded
     constants instead of actually fixing the reporting fails here.
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
FIXED_IN = "porphin_minimize_fixed.in"
MIN_DATA = "porphin_minimized.data"

SUMMARY_LABELS = {
    "e_initial": "Initial Energy:",
    "e_final": "Final Energy:",
    "delta_e": "Energy Change:",
}


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


def parse_summary(text, source):
    """Extract the three summary energies from LAMMPS output."""
    out = {}
    for key, label in SUMMARY_LABELS.items():
        m = re.search(rf"^\s*{re.escape(label)}\s+({NUM})\s+kcal/mol\s*$",
                      text, re.MULTILINE)
        check(m is not None,
              f"{source}: missing the '{label}' summary line in the required "
              f"format '<label>  <value> kcal/mol'")
        out[key] = float(m.group(1))
    return out


def last_loop_steps(text, source):
    loops = re.findall(
        r"Loop time of \S+ on \d+ procs for (\d+) steps with (\d+) atoms", text)
    check(bool(loops), f"{source}: no 'Loop time' line — nothing was run")
    steps, atoms = loops[-1]
    check(int(atoms) == N_ATOMS,
          f"{source}: run has {atoms} atoms (expected {N_ATOMS})")
    return int(steps)


def run_lammps(input_path, cwd, timeout=300):
    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run([LMP, "-in", input_path], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=timeout)
    return proc


with open(REFS_PATH) as f:
    refs = json.load(f)

LMP = shutil.which("lmp_serial") or "/usr/bin/lmp_serial"
check(os.path.isfile(LMP), "lmp_serial not found in the image — cannot recompute")

# ── Layer 1: File existence + schema ──────────────────────────────────────────
for fname in (FIXED_IN, "log.lammps", MIN_DATA, "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    try:
        results = json.load(f)
    except Exception as e:
        fail(f"results.json is not valid JSON: {e}")

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("e_initial", "e_final", "delta_e", "n_iterations"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

for key in ("e_initial", "e_final", "delta_e"):
    try:
        values[key] = float(values[key])
    except Exception:
        fail(f"results.json values[{key!r}] is not a number: {values[key]!r}")
try:
    values["n_iterations"] = int(values["n_iterations"])
except Exception:
    fail(f"results.json values['n_iterations'] is not an integer: "
         f"{values['n_iterations']!r}")

# ── Layer 2: Asset integrity ──────────────────────────────────────────────────
for rel, expected in refs["asset_hashes"].items():
    path = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(path), f"Pinned asset missing from the workspace: {rel}")
    actual = sha256_file(path)
    check(actual == expected,
          f"Asset {rel} was modified: {actual} != pinned {expected}")

# ── Layer 3: Fixed-input integrity (physics unchanged) ────────────────────────
with open(os.path.join(WORKSPACE, FIXED_IN)) as f:
    fixed_src = f.read()


def has_command(src, pattern):
    return re.search(pattern, src, re.MULTILINE | re.IGNORECASE) is not None


required_commands = {
    "bond_style harmonic": r"^\s*bond_style\s+harmonic\b",
    "angle_style harmonic": r"^\s*angle_style\s+harmonic\b",
    "dihedral_style fourier": r"^\s*dihedral_style\s+fourier\b",
    "improper_style cvff": r"^\s*improper_style\s+cvff\b",
    "pair_style lj/charmm/coul/long 8.0 10.0":
        r"^\s*pair_style\s+lj/charmm/coul/long\s+8\.0\s+10\.0\b",
    "kspace_style ewald 0.0001": r"^\s*kspace_style\s+ewald\s+0\.0001\b",
    "min_style cg": r"^\s*min_style\s+cg\b",
    "minimize 1.0e-4 1.0e-6 1000 10000":
        r"^\s*minimize\s+1\.0e-4\s+1\.0e-6\s+1000\s+10000\b",
}
for label, pattern in required_commands.items():
    check(has_command(fixed_src, pattern),
          f"{FIXED_IN} no longer contains '{label}' — the physics of the run "
          f"must stay identical; only the reporting may change")

check(has_command(fixed_src, r"^\s*read_data\s+\"?assets/system_gaff2\.data\"?"),
      f"{FIXED_IN} must read the structure via the relative path "
      f"'assets/system_gaff2.data'")
check(has_command(fixed_src,
                  r"^\s*include\s+\"?assets/system_gaff2\.in\.settings\"?"),
      f"{FIXED_IN} must include 'assets/system_gaff2.in.settings'")

for forbidden, pattern in {
    "special_bonds": r"^\s*special_bonds\b",
    "pair_modify": r"^\s*pair_modify\b",
    "velocity": r"^\s*velocity\b",
    "fix": r"^\s*fix\s+",
}.items():
    check(not has_command(fixed_src, pattern),
          f"{FIXED_IN} adds a '{forbidden}' command, which changes the run — "
          f"only the reporting logic may be modified")

# ── Layer 4: Log integrity + agreement with results.json ──────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Total wall time" in log_content,
      "log.lammps missing 'Total wall time' — run incomplete")
check(not re.search(r"^ERROR", log_content, re.MULTILINE),
      "log.lammps contains an ERROR line — the run did not complete cleanly")

log_summary = parse_summary(log_content, "log.lammps")
log_iterations = last_loop_steps(log_content, "log.lammps")
check(log_iterations > 0,
      "log.lammps records no minimisation iterations — the minimiser never ran")

cons_tol = refs["consistency_tol"]
for key in ("e_initial", "e_final", "delta_e"):
    check(abs(values[key] - log_summary[key]) <= cons_tol,
          f"results.json {key}={values[key]:.6f} does not match the value "
          f"printed in the agent's own log.lammps ({log_summary[key]:.6f}, "
          f"tol {cons_tol})")
check(values["n_iterations"] == log_iterations,
      f"results.json n_iterations={values['n_iterations']} != the "
      f"{log_iterations} iterations recorded in log.lammps")

# ── Layer 5: Numerical tolerance + internal closure ───────────────────────────
energy_tol = refs["energy_tol"]
for key in ("e_initial", "e_final", "delta_e"):
    ref = refs["energy_ref"][key]
    check(abs(values[key] - ref) <= energy_tol,
          f"{key}={values[key]:.6f} differs from the reference {ref:.6f} by "
          f"more than {energy_tol} kcal/mol")

check(abs(values["delta_e"] - (values["e_final"] - values["e_initial"]))
      <= refs["closure_tol"],
      f"delta_e={values['delta_e']:.6f} != e_final - e_initial = "
      f"{values['e_final'] - values['e_initial']:.6f}")
check(values["delta_e"] < 0,
      f"delta_e={values['delta_e']:.6f} is not negative — a minimisation must "
      f"lower the potential energy")

n_ref, n_tol = refs["n_iterations_ref"], refs["n_iterations_tol"]
check(abs(values["n_iterations"] - n_ref) <= n_tol,
      f"n_iterations={values['n_iterations']} differs from the reference "
      f"{n_ref} by more than {n_tol}")

# ── Layer 6: REAL RECOMPUTE of the written minimised structure ────────────────
# Styles are declared before read_data: a structure written by write_data
# carries its own Pair Coeffs section, which LAMMPS refuses to read until a
# pair_style exists.
SP_TEMPLATE = """units           real
atom_style      full
boundary        p p p

bond_style      harmonic
angle_style     harmonic
dihedral_style  fourier
improper_style  cvff
pair_style      lj/charmm/coul/long 8.0 10.0
kspace_style    ewald 0.0001

read_data       {data}

include         {settings}

neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes

thermo_style    custom step pe
thermo          1
run             0
"""


def single_point(data_path, settings_path, tag):
    """Potential energy of `data_path` from a fresh in-image LAMMPS run 0."""
    tmp = tempfile.mkdtemp(prefix=f"verify_sp_{tag}_")
    inp = os.path.join(tmp, "sp.in")
    with open(inp, "w") as f:
        f.write(SP_TEMPLATE.format(data=data_path, settings=settings_path))
    proc = run_lammps(inp, tmp)
    check(proc.returncode == 0,
          f"verifier single-point on {tag} failed (exit {proc.returncode}):\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    m = re.search(rf"^\s*Step\s+PotEng\s*$\n^\s*0\s+({NUM})",
                  proc.stdout, re.MULTILINE)
    if m is None:
        m = re.search(rf"^\s*0\s+({NUM})\s*$", proc.stdout, re.MULTILINE)
    check(m is not None,
          f"verifier could not read PotEng from the {tag} single point")
    shutil.rmtree(tmp, ignore_errors=True)
    return float(m.group(1))


settings_path = os.path.join(ASSETS, "system_gaff2.in.settings")
pe_written = single_point(os.path.join(WORKSPACE, MIN_DATA), settings_path,
                          "minimized")
rc_tol = refs["recompute_tol"]
check(abs(pe_written - values["e_final"]) <= rc_tol,
      f"RECOMPUTE: the in-image LAMMPS gives PotEng={pe_written:.6f} for your "
      f"{MIN_DATA}, but you reported e_final={values['e_final']:.6f} "
      f"(tol {rc_tol}) — the written structure is not the minimised one")

# ── Layer 7: GENERALISATION PROBE on a perturbed copy ─────────────────────────
def perturb_data(src_path, dst_path, amplitude):
    """Deterministically displace every atom; keeps the topology intact."""
    with open(src_path) as f:
        lines = f.read().splitlines()

    # The section header may carry a style comment, e.g. "Atoms  # full".
    try:
        start = next(i for i, l in enumerate(lines)
                     if re.match(r"^Atoms\b", l.strip())) + 1
    except StopIteration:
        fail("could not locate the Atoms section of the data file")
    while start < len(lines) and not lines[start].strip():
        start += 1

    out = list(lines)
    i, n = start, 0
    while i < len(lines) and lines[i].strip():
        parts = lines[i].split()
        if len(parts) < 7:
            break
        # atom_style full: id mol type q x y z [nx ny nz]
        aid = int(parts[0])
        for axis in range(3):
            col = 4 + axis
            # deterministic, mean-zero, amplitude-bounded displacement
            sign = 1.0 if ((aid + axis) % 2 == 0) else -1.0
            step = amplitude * sign * (1.0 + ((aid * 7 + axis * 13) % 5) / 8.0)
            parts[col] = f"{float(parts[col]) + step:.10f}"
        out[i] = " ".join(parts)
        i += 1
        n += 1

    check(n == N_ATOMS,
          f"perturbation rewrote {n} atom lines (expected {N_ATOMS})")
    with open(dst_path, "w") as f:
        f.write("\n".join(out) + "\n")


probe_dir = tempfile.mkdtemp(prefix="verify_probe_")
probe_assets = os.path.join(probe_dir, "assets")
os.makedirs(probe_assets, exist_ok=True)
shutil.copy(settings_path, os.path.join(probe_assets, "system_gaff2.in.settings"))
perturb_data(os.path.join(ASSETS, "system_gaff2.data"),
             os.path.join(probe_assets, "system_gaff2.data"),
             refs["probe_amplitude_ang"])

# The verifier's own ground truth for the perturbed system: initial PE from a
# single point, final PE + iteration count from a reference minimisation.
probe_e_initial = single_point(os.path.join(probe_assets, "system_gaff2.data"),
                               os.path.join(probe_assets,
                                            "system_gaff2.in.settings"),
                               "probe_initial")

ref_min_dir = tempfile.mkdtemp(prefix="verify_refmin_")
ref_min_in = os.path.join(ref_min_dir, "refmin.in")
with open(ref_min_in, "w") as f:
    f.write(SP_TEMPLATE.format(
        data=os.path.join(probe_assets, "system_gaff2.data"),
        settings=os.path.join(probe_assets, "system_gaff2.in.settings"),
    ).replace("run             0",
              "min_style       cg\nminimize        1.0e-4 1.0e-6 1000 10000"))
proc = run_lammps(ref_min_in, ref_min_dir, timeout=600)
check(proc.returncode == 0,
      f"verifier reference minimisation failed (exit {proc.returncode}):\n"
      f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
m = re.search(r"Energy initial, next-to-last, final\s*=\s*\n\s*"
              rf"({NUM})\s+({NUM})\s+({NUM})", proc.stdout)
check(m is not None,
      "verifier could not read the reference minimisation statistics")
probe_e_final = float(m.group(3))
probe_delta = probe_e_final - probe_e_initial
shutil.rmtree(ref_min_dir, ignore_errors=True)

# The probe is only meaningful if the perturbed system really has different
# energies from the pristine one. This is a self-check on the verifier, so it
# is measured against the calibrated reference, never against agent input.
discrimination = refs["probe_min_separation"]
pristine_e_initial = refs["energy_ref"]["e_initial"]
check(abs(probe_e_initial - pristine_e_initial) > discrimination,
      f"internal: the perturbation moved e_initial by only "
      f"{abs(probe_e_initial - pristine_e_initial):.4f} kcal/mol — the probe "
      f"cannot discriminate (expected > {discrimination})")

# Run the AGENT'S fixed input against the perturbed molecule.
shutil.copy(os.path.join(WORKSPACE, FIXED_IN),
            os.path.join(probe_dir, FIXED_IN))
proc = run_lammps(FIXED_IN, probe_dir, timeout=600)
check(proc.returncode == 0,
      f"PROBE: your {FIXED_IN} failed to run against a perturbed copy of the "
      f"same molecule (exit {proc.returncode}):\n"
      f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

probe_summary = parse_summary(proc.stdout, f"probe run of {FIXED_IN}")
probe_tol = refs["probe_tol"]
expected_probe = {
    "e_initial": probe_e_initial,
    "e_final": probe_e_final,
    "delta_e": probe_delta,
}
for key, expected in expected_probe.items():
    check(abs(probe_summary[key] - expected) <= probe_tol,
          f"PROBE: re-run against a perturbed copy of the molecule, your "
          f"{FIXED_IN} reports {key}={probe_summary[key]:.6f}, but the true "
          f"value for that system is {expected:.6f} (tol {probe_tol}). The "
          f"reporting is still not computed from the actual run.")

shutil.rmtree(probe_dir, ignore_errors=True)
print("PASS: lammps-minimize-var-bug")

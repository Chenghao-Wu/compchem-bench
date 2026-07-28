#!/usr/bin/env python3
"""
Verifier for lammps-npt-density-resolution:
  1. File existence + results.json schema (values/units)
  2. Asset integrity: every asset the verifier consumes is pinned by sha256
  3. Input integrity: both inputs are faithful instantiations of the
     template, differing only in the pressure and the output data file
  4. Log integrity: banner, footer, no ERROR, the exact thermo row count and
     step range, 1944 atoms, and the correct applied pressure per condition.
     Plus whole-trace integrity: every row's density must equal total mass /
     volume, and the two runs' density traces must actually diverge — a
     single pinned endpoint cannot police a fabricated trace
  5. Consistency: the verifier re-derives the window means, the block
     standard errors and kappa_T from the agent's own logs
  6. Internal closure: the difference, the combined SEM, the predicted
     density shift and the resolvable verdict must all follow from the
     agent's own reported numbers
  7. Physical plausibility: densities against the calibrated reference,
     block SEMs and kappa_T within physically sensible ranges
  8. The verdict: the predicted compressibility effect really is below this
     simulation's noise floor, so resolvable must be 0
  9. REAL RECOMPUTE: the two written configurations must differ, the density
     implied by each box must match the end of the corresponding log, and
     the in-image LAMMPS must reproduce that configuration's potential
     energy.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

WORKSPACE = "/workspace"
ASSETS = os.path.join(WORKSPACE, "assets")
REFS_PATH = "/tests/refs.json"

# A LAMMPS-formatted floating point number, incl. signed exponents.
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

N_ATOMS = 1944
N_MOLECULES = 216
M_ETHANOL = 46.069            # g/mol, C2H6O
N_AVOGADRO = 6.02214076e23

WINDOW_FROM = 10000           # window is step > WINDOW_FROM
N_BLOCKS = 4
K_B = 1.380649e-23            # J/K
T_REF = 298.0                 # K
ATM_PA = 101325.0
P_MARS_ATM = 0.005922

CONDITIONS = {
    "earth": {"input": "npt_earth.in", "log": "log_earth.lammps",
              "data": "after_npt_earth.data", "pressure": "1.0"},
    "mars": {"input": "npt_mars.in", "log": "log_mars.lammps",
             "data": "after_npt_mars.data", "pressure": "0.005922"},
}

SP_TEMPLATE = """units           real
atom_style      full
bond_style      harmonic
angle_style     harmonic
dihedral_style  opls
improper_style  cvff
pair_style      lj/charmm/coul/long 9.0 11.0
pair_modify     mix geometric
special_bonds   lj/coul 0.0 0.0 0.5
kspace_style    pppm 0.0001

read_data       {data}
include         {settings}
include         {charges}

neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes

thermo_style    custom step pe density
thermo          1
run             0
"""


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def close(a, b, tol):
    return abs(a - b) <= tol


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def thermo_rows(log_text, source):
    segments, cur = [], None
    for line in log_text.splitlines():
        s = line.strip()
        if re.match(r"^Step\s+", s, re.IGNORECASE):
            cur = []
            segments.append(cur)
            continue
        if cur is not None and re.match(r"^\d+\s+[-\d.eE+]", s):
            cur.append([float(x) for x in s.split()])
        if "Loop time" in line:
            cur = None
    check(bool(segments), f"{source}: no thermo table found")
    rows = np.array(segments[-1])
    check(rows.ndim == 2 and rows.shape[1] == 7,
          f"{source}: expected 7 thermo columns "
          f"(step temp press vol pe etotal density), got "
          f"{rows.shape[1] if rows.ndim == 2 else '?'}")
    return rows


def block_sem(x):
    size = len(x) // N_BLOCKS
    means = np.array([x[i * size:(i + 1) * size].mean() for i in range(N_BLOCKS)])
    return float(means.std(ddof=1) / np.sqrt(N_BLOCKS))


with open(REFS_PATH) as f:
    refs = json.load(f)

LMP = shutil.which("lmp_serial") or "/usr/bin/lmp_serial"
check(os.path.isfile(LMP), "lmp_serial not found in the image — cannot recompute")

# ── Layer 1: File existence + schema ──────────────────────────────────────────
required = ["results.json"]
for spec in CONDITIONS.values():
    required += [spec["input"], spec["log"], spec["data"]]
for fname in required:
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    try:
        results = json.load(f)
    except Exception as e:
        fail(f"results.json is not valid JSON: {e}")

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

FLOAT_KEYS = ("density_earth", "density_mars", "density_difference",
              "block_sem_earth", "block_sem_mars", "combined_sem",
              "kappa_T", "predicted_delta_rho")
INT_KEYS = ("n_window_rows", "resolvable")
for key in FLOAT_KEYS + INT_KEYS:
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
for key in FLOAT_KEYS:
    try:
        values[key] = float(values[key])
    except Exception:
        fail(f"results.json values[{key!r}] is not a number: {values[key]!r}")
for key in INT_KEYS:
    try:
        values[key] = int(values[key])
    except Exception:
        fail(f"results.json values[{key!r}] is not an integer: {values[key]!r}")
check(values["resolvable"] in (0, 1),
      f"resolvable must be 0 or 1, got {values['resolvable']}")

# ── Layer 2: Asset integrity ──────────────────────────────────────────────────
for rel, expected in refs["asset_hashes"].items():
    path = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(path), f"Pinned asset missing from the workspace: {rel}")
    actual = sha256_file(path)
    check(actual == expected,
          f"Asset {rel} was modified: {actual} != pinned {expected}")

# ── Layer 3: Input integrity (faithful template instantiation) ────────────────
with open(os.path.join(ASSETS, "npt_template.in")) as f:
    template = f.read()


def commands(text):
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        line = " ".join(line.split())
        if line:
            out.append(line)
    return out


for tag, spec in CONDITIONS.items():
    with open(os.path.join(WORKSPACE, spec["input"])) as f:
        agent_cmds = commands(f.read())
    expected_cmds = commands(template.replace("__PRESSURE__", spec["pressure"])
                                     .replace("__OUTDATA__", spec["data"]))
    check(agent_cmds == expected_cmds,
          f"{spec['input']} is not a faithful instantiation of "
          f"npt_template.in.\n  expected: {expected_cmds}\n"
          f"  found:    {agent_cmds}")

# ── Layer 4: Log integrity ────────────────────────────────────────────────────
log_stats = {}
for tag, spec in CONDITIONS.items():
    with open(os.path.join(WORKSPACE, spec["log"])) as f:
        log = f.read()
    name = spec["log"]

    check("LAMMPS" in log, f"{name} missing LAMMPS banner")
    check("Total wall time" in log,
          f"{name} missing 'Total wall time' — run incomplete")
    check(not re.search(r"^ERROR", log, re.MULTILINE),
          f"{name} contains an ERROR line — the run did not complete cleanly")
    check(not re.search(r"^\s*velocity\s+", log, re.MULTILINE),
          f"{name} records a 'velocity' command — both runs must continue from "
          f"the velocities stored in after_equil.data")

    m = re.search(rf"^\s*fix\s+\S+\s+all\s+npt\s+temp\s+298\.0\s+298\.0\s+50\.0"
                  rf"\s+iso\s+({NUM})\s+({NUM})\s+500\.0", log, re.MULTILINE)
    check(m is not None,
          f"{name} does not record the expected 'fix ... npt ... iso ...' line")
    check(close(float(m.group(1)), float(spec["pressure"]), 1e-9)
          and close(float(m.group(2)), float(spec["pressure"]), 1e-9),
          f"{name} applies pressure {m.group(1)}/{m.group(2)} atm, expected "
          f"{spec['pressure']} atm for the {tag} condition")

    loop = re.search(r"Loop time of \S+ on \d+ procs for (\d+) steps with "
                     r"(\d+) atoms", log)
    check(loop is not None, f"{name} has no 'Loop time' line — nothing was run")
    check(int(loop.group(1)) == refs["expected_steps"],
          f"{name} records a {loop.group(1)}-step run "
          f"(expected {refs['expected_steps']})")
    check(int(loop.group(2)) == N_ATOMS,
          f"{name} run has {loop.group(2)} atoms (expected {N_ATOMS})")

    rows = thermo_rows(log, name)
    check(len(rows) == refs["expected_thermo_rows"],
          f"{name} has {len(rows)} thermo rows "
          f"(expected {refs['expected_thermo_rows']})")
    check(int(rows[0][0]) == 0 and int(rows[-1][0]) == refs["expected_steps"],
          f"{name} spans steps {int(rows[0][0])}..{int(rows[-1][0])} "
          f"(expected 0..{refs['expected_steps']})")

    # Whole-trace integrity. LAMMPS' density column is total mass / volume by
    # construction, so EVERY row must satisfy that identity. This constrains
    # the entire trace, unlike a written configuration which pins one point.
    mass_g = N_MOLECULES * M_ETHANOL / N_AVOGADRO
    implied = mass_g / (rows[:, 3] * 1e-24)
    rel_dev = np.abs(implied - rows[:, 6]) / rows[:, 6]
    worst = int(np.argmax(rel_dev))
    check(rel_dev.max() <= refs["density_volume_rel_tol"],
          f"{name}: the density and volume columns are mutually inconsistent. "
          f"At step {int(rows[worst][0])} the volume {rows[worst][3]:.3f} A^3 "
          f"implies a density of {implied[worst]:.6f} g/cm^3, but the log "
          f"reports {rows[worst][6]:.6f} (relative deviation "
          f"{rel_dev.max():.2e}, tol {refs['density_volume_rel_tol']:.0e}) — "
          f"these columns come from the same configuration and cannot disagree")

    win = rows[rows[:, 0] > WINDOW_FROM]
    check(len(win) == refs["expected_window_rows"],
          f"{name}: the analysis window (step > {WINDOW_FROM}) holds "
          f"{len(win)} rows, expected {refs['expected_window_rows']}")

    log_stats[tag] = {
        "density_trace": rows[:, 6],
        "mean": float(win[:, 6].mean()),
        "sem": block_sem(win[:, 6]),
        "n": len(win),
        "volume": win[:, 3],
        "final_density": float(rows[-1][6]),
        "final_pe": float(rows[-1][4]),
    }

# Two runs at different pressures are two different trajectories: started
# from the same configuration they decorrelate, so their density traces
# cannot coincide. A Mars log copied from the Earth run fails here.
trace_rms = float(np.sqrt(((log_stats["earth"]["density_trace"]
                            - log_stats["mars"]["density_trace"]) ** 2).mean()))
check(trace_rms >= refs["min_trace_divergence"],
      f"the Earth and Mars density traces are near-identical (RMS difference "
      f"{trace_rms:.2e}, expected >= {refs['min_trace_divergence']:.0e}) — two "
      f"independent NPT trajectories decorrelate; one log was not produced by "
      f"a separate run")

# ── Layer 5: Consistency with the agent's own logs ────────────────────────────
cons_tol = refs["consistency_tol"]
for tag in CONDITIONS:
    check(close(values[f"density_{tag}"], log_stats[tag]["mean"], cons_tol),
          f"results.json density_{tag}={values[f'density_{tag}']:.6f} does not "
          f"match the verifier's re-average of your own "
          f"{CONDITIONS[tag]['log']} over step > {WINDOW_FROM} "
          f"({log_stats[tag]['mean']:.6f}, tol {cons_tol})")
    check(close(values[f"block_sem_{tag}"], log_stats[tag]["sem"], cons_tol),
          f"results.json block_sem_{tag}={values[f'block_sem_{tag}']:.6f} does "
          f"not match the verifier's block average over {N_BLOCKS} blocks of "
          f"{log_stats[tag]['n'] // N_BLOCKS} rows "
          f"({log_stats[tag]['sem']:.6f}, tol {cons_tol})")

check(values["n_window_rows"] == log_stats["earth"]["n"] == log_stats["mars"]["n"],
      f"n_window_rows={values['n_window_rows']} does not match the "
      f"{log_stats['earth']['n']} rows with step > {WINDOW_FROM} in the logs")

# kappa_T re-derived from the Earth run's volume trace
V = log_stats["earth"]["volume"] * 1e-30
kappa_log = float(((V - V.mean()) ** 2).mean() / (V.mean() * K_B * T_REF))
kappa_rel = refs["kappa_consistency_rel_tol"]
check(abs(values["kappa_T"] - kappa_log) <= kappa_rel * kappa_log,
      f"results.json kappa_T={values['kappa_T']:.4e} does not match the "
      f"verifier's re-derivation from the volume fluctuations of your own "
      f"{CONDITIONS['earth']['log']} ({kappa_log:.4e} /Pa, "
      f"tol {kappa_rel * 100:.0f}%)")

# ── Layer 6: Internal closure ─────────────────────────────────────────────────
closure_tol = refs["closure_tol"]
check(close(values["density_difference"],
            values["density_earth"] - values["density_mars"], closure_tol),
      f"density_difference={values['density_difference']:.6f} != "
      f"density_earth - density_mars = "
      f"{values['density_earth'] - values['density_mars']:.6f}")

expected_combined = float(np.sqrt(values["block_sem_earth"] ** 2
                                  + values["block_sem_mars"] ** 2))
check(close(values["combined_sem"], expected_combined, closure_tol),
      f"combined_sem={values['combined_sem']:.6f} != "
      f"sqrt(block_sem_earth^2 + block_sem_mars^2) = {expected_combined:.6f}")

delta_P = (1.0 - P_MARS_ATM) * ATM_PA
expected_pred = values["density_earth"] * values["kappa_T"] * delta_P
check(abs(values["predicted_delta_rho"] - expected_pred)
      <= refs["prediction_rel_tol"] * max(expected_pred, 1e-12),
      f"predicted_delta_rho={values['predicted_delta_rho']:.3e} != "
      f"density_earth * kappa_T * delta_P = {expected_pred:.3e} "
      f"(delta_P = {delta_P:.0f} Pa)")

implied = int(values["predicted_delta_rho"] > values["combined_sem"])
check(values["resolvable"] == implied,
      f"resolvable={values['resolvable']} contradicts your own numbers: "
      f"predicted_delta_rho={values['predicted_delta_rho']:.3e} vs "
      f"combined_sem={values['combined_sem']:.3e} implies {implied}")

# ── Layer 7: Physical plausibility ────────────────────────────────────────────
rho_tol = refs["density_tol"]
for tag in CONDITIONS:
    ref = refs["density_ref"][tag]
    check(close(values[f"density_{tag}"], ref, rho_tol),
          f"density_{tag}={values[f'density_{tag}']:.6f} differs from the "
          f"reference {ref:.6f} by more than {rho_tol} g/cm^3")

sem_lo, sem_hi = refs["block_sem_range"]
for tag in CONDITIONS:
    sem = values[f"block_sem_{tag}"]
    check(sem_lo <= sem <= sem_hi,
          f"block_sem_{tag}={sem:.6f} is outside the physically expected "
          f"range [{sem_lo}, {sem_hi}] g/cm^3 for this system and window")

k_lo, k_hi = refs["kappa_range"]
check(k_lo <= values["kappa_T"] <= k_hi,
      f"kappa_T={values['kappa_T']:.4e} /Pa is outside the physically "
      f"sensible range [{k_lo:.1e}, {k_hi:.1e}] for a molecular liquid — "
      f"check the unit conversion from cubic angstroms")

# ── Layer 8: The verdict ──────────────────────────────────────────────────────
check(values["resolvable"] == refs["resolvable_ref"],
      f"resolvable={values['resolvable']} but the reference runs give "
      f"{refs['resolvable_ref']}: the compressibility of liquid ethanol puts "
      f"the Earth-to-Mars density shift far below the block-averaged noise "
      f"floor of a run this short")

margin = values["combined_sem"] / max(values["predicted_delta_rho"], 1e-12)
check(margin >= refs["min_resolution_margin"],
      f"internal: the noise floor is only {margin:.1f}x the predicted effect "
      f"(expected >= {refs['min_resolution_margin']}x) — the premise of the "
      f"task does not hold for these runs")

# ── Layer 9: REAL RECOMPUTE from the written configurations ───────────────────
settings = os.path.join(ASSETS, "system.in.settings")
charges = os.path.join(ASSETS, "system.in.charges")
env = dict(os.environ, OMP_NUM_THREADS="1")


def box_density(data_path):
    """Density implied by the box bounds written into a LAMMPS data file."""
    lengths = {}
    with open(data_path) as f:
        for line in f:
            m = re.match(rf"\s*({NUM})\s+({NUM})\s+([xyz])lo\s+\3hi", line)
            if m:
                lengths[m.group(3)] = float(m.group(2)) - float(m.group(1))
            if line.strip().startswith("Atoms"):
                break
    check(set(lengths) == {"x", "y", "z"},
          f"could not read the box bounds from {os.path.basename(data_path)}")
    volume_cm3 = lengths["x"] * lengths["y"] * lengths["z"] * 1e-24
    mass_g = N_MOLECULES * M_ETHANOL / N_AVOGADRO
    return mass_g / volume_cm3


box_tol = refs["box_density_tol"]
pe_tol = refs["recompute_pe_tol"]

# The two runs end in different configurations. Handing over one file twice
# is the cheapest way to fake the second run, and is exact to detect.
earth_data = os.path.join(WORKSPACE, CONDITIONS["earth"]["data"])
mars_data = os.path.join(WORKSPACE, CONDITIONS["mars"]["data"])
check(sha256_file(earth_data) != sha256_file(mars_data),
      f"{CONDITIONS['earth']['data']} and {CONDITIONS['mars']['data']} are "
      f"byte-identical — the same configuration was handed over for both "
      f"conditions, so only one simulation was actually run")

for tag, spec in CONDITIONS.items():
    data_path = os.path.join(WORKSPACE, spec["data"])

    rho_box = box_density(data_path)
    check(close(rho_box, log_stats[tag]["final_density"], box_tol),
          f"RECOMPUTE: the box in your {spec['data']} implies a density of "
          f"{rho_box:.6f} g/cm^3, but {spec['log']} ends at "
          f"{log_stats[tag]['final_density']:.6f} (tol {box_tol}) — the "
          f"written configuration is not the end of that run")

    tmp = tempfile.mkdtemp(prefix=f"verify_sp_{tag}_")
    inp = os.path.join(tmp, "sp.in")
    with open(inp, "w") as f:
        f.write(SP_TEMPLATE.format(data=data_path, settings=settings,
                                   charges=charges))
    proc = subprocess.run([LMP, "-in", inp], cwd=tmp, env=env,
                          capture_output=True, text=True, timeout=300)
    check(proc.returncode == 0,
          f"verifier single-point on {spec['data']} failed "
          f"(exit {proc.returncode}):\n{proc.stdout[-2000:]}\n"
          f"{proc.stderr[-2000:]}")
    m = re.search(rf"^\s*0\s+({NUM})\s+({NUM})\s*$", proc.stdout, re.MULTILINE)
    check(m is not None,
          f"verifier could not read PotEng from the {spec['data']} single point")
    pe_written = float(m.group(1))
    shutil.rmtree(tmp, ignore_errors=True)

    check(close(pe_written, log_stats[tag]["final_pe"], pe_tol),
          f"RECOMPUTE: the in-image LAMMPS gives PotEng={pe_written:.4f} for "
          f"your {spec['data']}, but {spec['log']} ends at "
          f"PotEng={log_stats[tag]['final_pe']:.4f} (tol {pe_tol}) — that "
          f"configuration did not come out of the run you reported")

print("PASS: lammps-npt-density-resolution")

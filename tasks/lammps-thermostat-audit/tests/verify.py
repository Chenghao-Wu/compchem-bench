#!/usr/bin/env python3
"""
Verifier for lammps-thermostat-audit:
  1. File existence + results.json schema (values/units)
  2. fixed.in semantics: thermostat applied to ALL atoms at T*=1.2, sane
     timestep, same 5000-step run — a run of the unmodified broken input
     fails here
  3. Log integrity + average temperature within 3% of the target
  4. Consistency: results.json avg_temp == mean of the log's T over
     steps >= 2500
  5. L4 REAL RECOMPUTE from state.dump (id type x y z vx vy vz):
     (a) kinetic temperature from the last-frame velocities must match the
         log's Temp at that step
     (b) 0-step LAMMPS re-evaluation of the last-frame positions must
         match the log's PotEng at that step
     Fabricated state dumps (consistent-looking positions/velocities that
     were never simulated) cannot pass both.
"""
import json
import sys
import os
import re
import subprocess
import tempfile
import shutil

import numpy as np

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

N_ATOMS = 500
DT_DEFAULT_CHECK = 0.006


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("fixed.in", "log.lammps", "state.dump", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("avg_temp", "final_step"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: fixed.in semantics ────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "fixed.in")) as f:
    fixed = f.read()

# Strip comments for semantic checks
fixed_nc = re.sub(r"#.*", "", fixed)

check(re.search(r"^\s*fix\s+\S+\s+all\s+nvt\s+temp\s+1\.2\s+1\.2\b", fixed_nc, re.MULTILINE),
      "fixed.in must thermostat ALL atoms with 'fix <id> all nvt temp 1.2 1.2 ...' "
      "— the broken input only thermostats half the fluid")
check(not re.search(r"^\s*fix\s+\S+\s+(?!all\b)\S+\s+nvt\b", fixed_nc, re.MULTILINE),
      "fixed.in still applies an NVT fix to a subgroup — thermostat the whole fluid")

m = re.search(r"^\s*timestep\s+([\d.eE+]+)", fixed_nc, re.MULTILINE)
check(m is not None, "fixed.in has no timestep command")
dt = float(m.group(1))
check(dt <= DT_DEFAULT_CHECK,
      f"fixed.in timestep {dt} is too large for an LJ fluid at T*~1.2 "
      f"(must be <= {DT_DEFAULT_CHECK})")

check(re.search(r"^\s*run\s+5000\b", fixed_nc, re.MULTILINE),
      "fixed.in must keep 'run 5000'")
check(re.search(r"^\s*velocity\s+all\s+create\s+1\.2\s+2718", fixed_nc, re.MULTILINE),
      "fixed.in must keep the pinned velocity seed (1.2 2718)")

# ── Layer 3: Log integrity + average temperature ──────────────────────────────
with open(os.path.join(WORKSPACE, "log.lammps")) as f:
    log_content = f.read()

check("LAMMPS" in log_content, "log.lammps missing LAMMPS banner")
check("Total wall time" in log_content,
      "log.lammps missing 'Total wall time' — run incomplete")
check("ERROR" not in log_content, "log.lammps contains ERROR lines")

thermo = []
in_run = False
for line in log_content.splitlines():
    s = line.strip()
    if re.match(r"^Step\s+", s, re.IGNORECASE):
        in_run = True
        continue
    if in_run and re.match(r"^\d+\s+[-\d.eE+]+", s):
        thermo.append(s)
    if "Loop time" in line:
        in_run = False

n_expected = refs["expected_thermo_lines"]
check(len(thermo) == n_expected,
      f"Expected {n_expected} thermo lines (0..5000 every 100), got {len(thermo)}")
check(int(thermo[0].split()[0]) == 0 and int(thermo[-1].split()[0]) == 5000,
      f"Thermo must cover steps 0..5000, got {thermo[0].split()[0]}.."
      f"{thermo[-1].split()[0]}")

steps = np.array([int(l.split()[0]) for l in thermo])
temps = np.array([float(l.split()[1]) for l in thermo])
log_avg_temp = float(temps[steps >= 2500].mean())

target, tol_frac = refs["target_temp"], refs["avg_temp_tol_frac"]
check(abs(log_avg_temp - target) / target <= tol_frac,
      f"average temperature {log_avg_temp:.4f} deviates from target {target} by "
      f">{tol_frac*100:.0f}% — the thermostat is not holding the fluid at T*")

check(values["final_step"] == 5000, f"final_step must be 5000, got {values['final_step']}")

# ── Layer 4: Consistency results.json ↔ log ────────────────────────────────────
check(abs(values["avg_temp"] - log_avg_temp) <= refs["avg_temp_consistency_tol"],
      f"results.json avg_temp={values['avg_temp']:.5f} != log-derived "
      f"{log_avg_temp:.5f} (tol {refs['avg_temp_consistency_tol']})")

# ── Layer 5: L4 REAL RECOMPUTE from state.dump ────────────────────────────────
frames = []
with open(os.path.join(WORKSPACE, "state.dump")) as f:
    lines = f.read().splitlines()

i = 0
while i < len(lines):
    check(lines[i].startswith("ITEM: TIMESTEP"),
          f"state.dump: malformed frame at line {i+1}")
    step = int(lines[i + 1])
    n = int(lines[i + 3])
    check(n == N_ATOMS, f"state.dump frame {step} has {n} atoms (expected {N_ATOMS})")
    check(lines[i + 4].startswith("ITEM: BOX BOUNDS"),
          f"state.dump: missing BOX BOUNDS at line {i+5}")
    box = []
    for j in range(3):
        lo, hi = lines[i + 5 + j].split()[:2]
        box.append((float(lo), float(hi)))
    i += 8
    cols = lines[i].split()[2:]
    for need in ("id", "type", "x", "y", "z", "vx", "vy", "vz"):
        check(need in cols, f"state.dump must contain column {need!r} (found {cols})")
    idx = {c: cols.index(c) for c in ("id", "type", "x", "y", "z", "vx", "vy", "vz")}
    recs = []
    for k in range(n):
        p = lines[i + 1 + k].split()
        recs.append((int(p[idx["id"]]), int(p[idx["type"]]),
                     float(p[idx["x"]]), float(p[idx["y"]]), float(p[idx["z"]]),
                     float(p[idx["vx"]]), float(p[idx["vy"]]), float(p[idx["vz"]])))
    recs.sort(key=lambda r: r[0])
    frames.append((step, box, recs))
    i += 1 + n

check(len(frames) == refs["n_frames_expected"],
      f"state.dump has {len(frames)} frames (expected {refs['n_frames_expected']})")
last_step, last_box, last_recs = frames[-1]
check(last_step == 5000, f"last state.dump frame at step {last_step} (expected 5000)")

# (a) kinetic temperature from velocities ≡ log Temp at the same step
v2 = sum(r[5] ** 2 + r[6] ** 2 + r[7] ** 2 for r in last_recs)
T_kin = v2 / (3 * N_ATOMS - 3)
log_last = thermo[-1].split()
log_T_last, log_pe_last = float(log_last[1]), float(log_last[2])
check(abs(T_kin - log_T_last) / max(log_T_last, 1e-9) <= refs["l4_temp_tol_frac"],
      f"L4: kinetic temperature from state.dump velocities {T_kin:.5f} != log "
      f"Temp {log_T_last:.5f} at step 5000 (tol {refs['l4_temp_tol_frac']*100:.0f}%) "
      f"— the velocities are not from the claimed run")

# (b) 0-step PE re-evaluation of the last-frame positions ≡ log PotEng
data_lines = ["L4 recompute of state.dump final frame", "",
              f"{N_ATOMS} atoms", "2 atom types", ""]
for j, name in enumerate(("x", "y", "z")):
    data_lines.append(f"{last_box[j][0]:.8f} {last_box[j][1]:.8f} {name}lo {name}hi")
data_lines += ["", "Masses", "", "1 1.0", "2 1.0", "", "Atoms # atomic", ""]
for r in last_recs:
    data_lines.append(f"{r[0]} {r[1]} {r[2]:.8f} {r[3]:.8f} {r[4]:.8f}")

recompute_input = """units           lj
atom_style      atomic
boundary        p p p
pair_style      lj/cut 2.5
read_data       frame.data
pair_coeff      1 1 1.0 1.0 2.5
pair_coeff      1 2 1.0 1.0 2.5
pair_coeff      2 2 1.0 1.0 2.5
neighbor        0.3 bin
neigh_modify    every 20 delay 0 check no
thermo          1
thermo_style    custom step pe
run             0
"""

tmpdir = tempfile.mkdtemp(prefix="l4_recompute_")
try:
    with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
        f.write(recompute_input)
    with open(os.path.join(tmpdir, "frame.data"), "w") as f:
        f.write("\n".join(data_lines) + "\n")

    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["lmp_serial", "-in", "recompute.in"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=180,
    )
    check(proc.returncode == 0,
          f"L4: LAMMPS could not evaluate the dumped final frame "
          f"(exit {proc.returncode}):\n{proc.stdout[-1500:]}")
    th = re.findall(r"^\s*0\s+([-\d.eE+]+)\s*$", proc.stdout, re.MULTILINE)
    check(th, "L4: no thermo output from the 0-step run on the dumped frame")
    re_pe = float(th[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

check(abs(re_pe - log_pe_last) <= refs["l4_pe_tol"],
      f"L4: recomputed PE/atom of the dumped final frame {re_pe:.6f} != log "
      f"PotEng {log_pe_last:.6f} (tol {refs['l4_pe_tol']}) — the positions are "
      f"not from the claimed run")

print("PASS: lammps-thermostat-audit")

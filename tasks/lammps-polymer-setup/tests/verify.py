#!/usr/bin/env python3
"""
Verifier for lammps-polymer-setup:
  1. File existence + results.json schema (values/units)
  2. Topology of polymer.data: 200 atoms / 1 atom type / mass 1.0 /
     190 bonds / 1 bond type; bond graph must be exactly 10 chains of 20
     (20 endpoints, 180 degree-2 beads, 10 connected components)
  3. Density: box volume from polymer.data, rho = 0.85 +/- tol
  4. Log integrity: banner, footer, no ERROR, 31 thermo rows (0..3000);
     final PE inside the plausibility window (agent-built initial configs
     legitimately differ — the window is wide on purpose)
  5. Consistency: results.json vs files/log
  6. L4a REAL READ: read_data + run 0 on polymer.data with the exact
     Kremer-Grest force field -> PE must be finite and match the log's
     FIRST thermo line (the initial state is what the run claims to start
     from)
  7. Evolution: initial vs final configurations must differ (real dynamics)
  8. L4b REAL READ: read_data + run 0 on final.data -> PE must match the
     log's LAST thermo line
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

N_ATOMS = 200
N_BONDS = 190


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("polymer.data", "log.lammps", "final.data", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("n_atoms", "n_bonds", "density", "final_pe"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")


def parse_data(path):
    """Parse a LAMMPS data file (atom_style molecular/full) ->
    (box_lens, atoms {id: (type, xyz)}, bonds [(a1, a2)], masses {type: m})."""
    with open(path) as f:
        text = f.read()

    box_m = re.findall(r"^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+[xyz]lo [xyz]hi\s*$",
                       text, re.MULTILINE)
    check(len(box_m) == 3, f"{path}: expected 3 box lines")
    box = [float(b[1]) - float(b[0]) for b in box_m]

    mm = re.search(r"Masses[^\n]*\n\s*\n((?:[^\S\n]*\d+[^\S\n]+[\d.]+[^\n]*\n?)+)", text)
    check(mm is not None, f"{path}: no parseable Masses section")
    masses = {}
    for line in mm.group(1).strip().splitlines():
        p = line.split()
        if len(p) >= 2:
            masses[int(p[0])] = float(p[1])

    am = re.search(r"Atoms[^\n]*\n\s*\n((?:[^\S\n]*\d+[^\n]*\n?)+)", text)
    check(am is not None, f"{path}: no parseable Atoms section")
    atoms = {}
    for line in am.group(1).strip().splitlines():
        p = line.split()
        if len(p) < 6:
            continue
        aid = int(p[0])
        # molecular style: id mol type x y z
        atype = int(p[2])
        xyz = (float(p[3]), float(p[4]), float(p[5]))
        check(aid not in atoms, f"{path}: duplicate atom id {aid}")
        atoms[aid] = (atype, xyz)

    bonds = []
    bm = re.search(r"Bonds[^\n]*\n\s*\n((?:[^\S\n]*\d+[^\n]*\n?)+)", text)
    if bm is not None:
        for line in bm.group(1).strip().splitlines():
            p = line.split()
            if len(p) >= 4:
                bonds.append((int(p[2]), int(p[3])))
    return box, atoms, bonds, masses, text


# ── Layer 2: Topology of polymer.data ─────────────────────────────────────────
box, atoms, bonds, masses, _ = parse_data(os.path.join(WORKSPACE, "polymer.data"))

check(len(atoms) == N_ATOMS, f"polymer.data has {len(atoms)} atoms (expected {N_ATOMS})")
check(set(a[0] for a in atoms.values()) == {1},
      f"polymer.data must use a single atom type, got {set(a[0] for a in atoms.values())}")
check(masses.get(1) == 1.0, f"polymer.data mass of type 1 must be 1.0, got {masses.get(1)}")
check(len(bonds) == N_BONDS, f"polymer.data has {len(bonds)} bonds (expected {N_BONDS})")

degree = {}
for a1, a2 in bonds:
    check(a1 in atoms and a2 in atoms, f"polymer.data bond references unknown atom {a1}-{a2}")
    check(a1 != a2, "polymer.data contains a self-bond")
    degree[a1] = degree.get(a1, 0) + 1
    degree[a2] = degree.get(a2, 0) + 1
check(len(degree) == N_ATOMS, "polymer.data: some atoms are not in any bond")
check(max(degree.values()) <= 2, "polymer.data: an atom has more than 2 bonds (branched?)")
n_end = sum(1 for d in degree.values() if d == 1)
n_mid = sum(1 for d in degree.values() if d == 2)
check(n_end == 2 * refs["n_chains_expected"] and n_mid == N_ATOMS - 2 * refs["n_chains_expected"],
      f"polymer.data must be {refs['n_chains_expected']} linear chains: "
      f"{n_end} endpoints / {n_mid} degree-2 beads")

# Connected components via union-find
parent = {a: a for a in atoms}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


for a1, a2 in bonds:
    parent[find(a1)] = find(a2)

comp_sizes = {}
for a in atoms:
    r = find(a)
    comp_sizes[r] = comp_sizes.get(r, 0) + 1
sizes = sorted(comp_sizes.values())
check(sizes == [N_ATOMS // refs["n_chains_expected"]] * refs["n_chains_expected"],
      f"polymer.data bond graph components {sizes} != "
      f"{refs['n_chains_expected']} chains of {N_ATOMS // refs['n_chains_expected']}")

# ── Layer 3: Density ───────────────────────────────────────────────────────────
vol = box[0] * box[1] * box[2]
rho = N_ATOMS / vol
check(abs(rho - 0.85) <= refs["density_tol"],
      f"polymer.data density {rho:.4f} != 0.85 (tol {refs['density_tol']})")

# ── Layer 4: Log integrity + final PE plausibility ────────────────────────────
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

check(len(thermo) == refs["expected_thermo_lines"],
      f"Expected {refs['expected_thermo_lines']} thermo rows (0..3000 every 100), "
      f"got {len(thermo)}")
check(int(thermo[0].split()[0]) == 0 and int(thermo[-1].split()[0]) == 3000,
      f"Thermo must cover steps 0..3000, got {thermo[0].split()[0]}.."
      f"{thermo[-1].split()[0]}")

log_first_pe = float(thermo[0].split()[2])
log_last_pe = float(thermo[-1].split()[2])

check(refs["final_pe_min"] <= log_last_pe <= refs["final_pe_max"],
      f"log final PE/atom {log_last_pe} outside the plausibility window "
      f"[{refs['final_pe_min']}, {refs['final_pe_max']}] for a Kremer-Grest melt "
      f"after 3000 NVT steps")

# ── Layer 5: Consistency results.json ↔ files/log ─────────────────────────────
check(values["n_atoms"] == len(atoms),
      f"results.json n_atoms={values['n_atoms']} != polymer.data {len(atoms)}")
check(values["n_bonds"] == len(bonds),
      f"results.json n_bonds={values['n_bonds']} != polymer.data {len(bonds)}")
check(abs(values["density"] - rho) <= refs["density_tol"],
      f"results.json density={values['density']} != polymer.data {rho:.4f}")
check(abs(values["final_pe"] - log_last_pe) <= refs["consistency_pe_tol"],
      f"results.json final_pe={values['final_pe']} != log last line {log_last_pe}")

# ── Layer 6: L4a REAL READ — run 0 on the initial polymer.data ────────────────
RECOMPUTE = """units           lj
atom_style      molecular
boundary        p p p
bond_style      fene
special_bonds   fene
pair_style      lj/cut 1.12246204830937
read_data       {data}
pair_coeff      * * 1.0 1.0 1.12246204830937
pair_modify     shift yes
bond_coeff      1 30.0 1.5 1.0 1.0
neighbor        0.4 bin
neigh_modify    every 1 delay 0 check yes
thermo          1
thermo_style    custom step pe
run             0
"""


def run0_pe(data_path):
    tmpdir = tempfile.mkdtemp(prefix="l4_read_")
    try:
        with open(os.path.join(tmpdir, "recompute.in"), "w") as f:
            f.write(RECOMPUTE.format(data="system.data"))
        shutil.copy(data_path, os.path.join(tmpdir, "system.data"))
        env = dict(os.environ, OMP_NUM_THREADS="1")
        proc = subprocess.run(
            ["lmp_serial", "-in", "recompute.in"],
            cwd=tmpdir, env=env, capture_output=True, text=True, timeout=180,
        )
        check(proc.returncode == 0,
              f"L4: LAMMPS could not read/run {os.path.basename(data_path)} "
              f"(exit {proc.returncode}):\n{proc.stdout[-1500:]}")
        th = re.findall(r"^\s*0\s+([-\d.eE+]+|nan|-nan|inf|-inf)\s*$",
                        proc.stdout, re.MULTILINE)
        check(th, "L4: no thermo output from the 0-step run")
        pe = float(th[-1])
        check(pe == pe and abs(pe) != float("inf"),
              f"L4: run-0 energy of {os.path.basename(data_path)} is not finite "
              f"({pe}) — the initial configuration overlaps")
        return pe
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


pe_initial = run0_pe(os.path.join(WORKSPACE, "polymer.data"))
check(abs(pe_initial - log_first_pe) <= refs["l4_pe_tol"],
      f"L4: run-0 PE/atom of polymer.data {pe_initial:.6f} != log first thermo "
      f"line {log_first_pe:.6f} (tol {refs['l4_pe_tol']}) — the initial "
      f"configuration is not the one the run claims to start from")

# ── Layer 7: Evolution — initial vs final must differ ─────────────────────────
fbox, fatoms, fbonds, _, _ = parse_data(os.path.join(WORKSPACE, "final.data"))
check(len(fatoms) == N_ATOMS, f"final.data has {len(fatoms)} atoms (expected {N_ATOMS})")
check(len(fbonds) == N_BONDS, f"final.data has {len(fbonds)} bonds (expected {N_BONDS})")
disp = [np.linalg.norm(np.array(fatoms[a][1]) - np.array(atoms[a][1]))
        for a in atoms if a in fatoms]
rms = float(np.sqrt(np.mean(np.square(disp))))
check(rms >= refs["evolution_rms_min"],
      f"RMS displacement between polymer.data and final.data is {rms:.4f}σ "
      f"(< {refs['evolution_rms_min']}) — the system did not evolve; the run "
      f"is not real")

# ── Layer 8: L4b REAL READ — run 0 on final.data ──────────────────────────────
pe_final = run0_pe(os.path.join(WORKSPACE, "final.data"))
check(abs(pe_final - log_last_pe) <= refs["l4_pe_tol"],
      f"L4: run-0 PE/atom of final.data {pe_final:.6f} != log last thermo line "
      f"{log_last_pe:.6f} (tol {refs['l4_pe_tol']}) — final.data is not the "
      f"genuine end state of the claimed run")

print("PASS: lammps-polymer-setup")

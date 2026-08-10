#!/usr/bin/env python3
"""
Verifier for lammps-thermal-conductivity (reworked).

The agent must: (1) build the 1200-bead sticker melt with the provided template
script, (2) equilibrate at T*=1.0, (3) quench to T*=0.4 starting from the T*=1.0
state, (4) run a 200000-step NVE production at T*=0.4, and (5) compute kappa at
T*=0.4 by the reference protocol.

Layers:
 1.  File existence + results.json values/units schema
 1b. System authenticity: the provided generator is deterministic, so the
     verifier re-runs the pinned asset and byte-compares the agent's data.in.
     A fabricated data.in (or a modified generator) fails here.
 2.  Log integrity: banner / completion / atom count for all three LAMMPS runs;
     mean temperature of each stage; exact thermo-row count and NVE energy
     conservation on the production run only (the eq runs are thermostatted).
 2b. Data structure: both equilibrated data files = 1200 atoms, 2 types, 60
     stickers, 1170 bonds, 1140 angles, expected box, velocities present.
 3.  HCACF structure: 8 complete blocks x 200 lags, lag-0 Ncount, positive G(0).
 4.  Numerical tolerance: kappa_T04 within tolerance of the calibrated reference.
 5.  Consistency: the verifier re-derives kappa from the J0Jt file with the
     reference protocol - must match results.json.
 6.  REAL RECOMPUTE: the verifier computes the HCACF from the raw flux_*.dat
     series and integrates it again; kappa and <J^2> must match.
"""
import json
import sys
import os
import re
import subprocess
import hashlib

import numpy as np

WORKSPACE = os.environ.get("GK_WORKSPACE", "/workspace")
REFS_PATH = os.environ.get("GK_REFS", "/tests/refs.json")

DT = 0.005
NEVERY = 5
DT_DATA = NEVERY * DT          # lag spacing in tau
KBT = 1.0
WINDOW = 10
NLAGS = 200
TARGET_T04 = 0.4


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)


# ── shared analysis helpers ──────────────────────────────────────────────────────

def parse_acf(path):
    """Blocks of rows (index, TimeDelta, Ncount, c1, c2, c3)."""
    blocks = []
    cur = None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) == 2:
                try:
                    int(parts[0]); int(parts[1])
                except ValueError:
                    continue
                cur = []
                blocks.append(cur)
                continue
            if len(parts) >= 6 and cur is not None:
                try:
                    cur.append([float(x) for x in parts[:6]])
                except ValueError:
                    continue
    return blocks


def parse_flux(path):
    ts, jx, jy, jz = [], [], [], []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            p = s.split()
            if len(p) < 4:
                continue
            try:
                ts.append(float(p[0])); jx.append(float(p[1]))
                jy.append(float(p[2])); jz.append(float(p[3]))
            except ValueError:
                continue
    return np.array(ts), np.array(jx), np.array(jy), np.array(jz)


def kappa_from_G(G, V, T):
    """Reference protocol: smooth-normalize, zero-crossing cutoff, integrate."""
    Gn = G / G[0]
    smooth = np.convolve(Gn, np.ones(WINDOW) / WINDOW, mode="valid")
    zeros = np.where(smooth < 0)[0]
    cutoff = int(round((zeros[0] + WINDOW) * 1.5)) if len(zeros) else len(G)
    cutoff = min(cutoff, len(G))
    integ = np.cumsum(G[:cutoff]) * DT_DATA
    curve = integ / (3.0 * KBT * T * T * V)
    return float(np.mean(curve[int(len(curve) * 0.8):])), cutoff


def avg_acf(blocks):
    """Average G(t) = c1+c2+c3 over complete blocks; (G array, n_complete)."""
    full = [b for b in blocks if len(b) >= NLAGS and b[0][2] >= refs["ncount_lag0_ref"]]
    if not full:
        return None, 0
    G = np.zeros(NLAGS)
    for b in full:
        a = np.array(b)[:NLAGS]
        G += a[:, 3] + a[:, 4] + a[:, 5]
    return G / len(full), len(full)


def parse_thermo(logpath):
    """Thermo rows of the LAST run section in a LAMMPS log.

    LAMMPS emits one section per 'run' (and per 'minimize'). A section starts at
    a 'Step' header line and runs until the next 'Loop time'. The equilibration
    logs carry a short minimize section first, so we keep the last completed
    section (the production/equilibration run).
    """
    sections = []
    cur = None
    for line in open(logpath):
        t = line.strip()
        if re.match(r"^Step\s+", t, re.IGNORECASE):
            cur = []
            continue
        if cur is None:
            continue
        if "Loop time" in line:
            if cur:
                sections.append(cur)
            cur = None
            continue
        if re.match(r"^\d+\s+", t):
            p = t.split()
            try:
                cur.append([float(x) for x in p])
            except ValueError:
                pass
    if cur:
        sections.append(cur)
    return sections[-1] if sections else []


def parse_data(path):
    """Header counts, per-type atom counts, box bounds, has-velocities."""
    counts = {}
    types = {}
    box = {}
    section = None
    has_vel = False
    for raw in open(path):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        if p[0] in ("Atoms", "Velocities", "Bonds", "Angles", "Masses",
                    "Dihedrals", "Impropers"):
            if p[0] == "Velocities":
                has_vel = True
            section = p[0]
            continue
        if section is None:
            if len(p) == 2 and p[1] in ("atoms", "bonds", "angles",
                                        "dihedrals", "impropers"):
                counts[p[1]] = int(p[0])
            elif len(p) == 4 and p[2] in ("xlo", "ylo", "zlo"):
                box[p[2]] = (float(p[0]), float(p[1]))
        elif section == "Atoms" and len(p) >= 3 and p[0].isdigit():
            types[int(p[2])] = types.get(int(p[2]), 0) + 1
    return counts, types, box, has_vel


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── L0 asset integrity (pinned assets must be unmodified) ─────────────────────────

for rel, digest in refs.get("asset_hashes", {}).items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"missing asset: {rel}")
    check("sha256:" + sha256(p) == digest,
          f"asset {rel} does not match pinned sha256 (modified/tampered?)")

# ── L1: file existence + results.json schema ─────────────────────────────────────

for fname in ("data.in", "data_T1.lammps", "data_T04.lammps",
              "log.eq_T1", "log.eq_T04", "log.T04",
              "J0Jt_T04.dat", "flux_T04.dat", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("kappa_T04", "kappa_err_T04", "n_blocks"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── L1b: system authenticity (deterministic generator, byte-compare) ─────────────

gen_asset = os.path.join(WORKSPACE, "assets", "generate_bench_system.py")
ref_data = os.path.join(WORKSPACE, "ref_data.in")  # inside the container
r = subprocess.run(["python3", gen_asset, ref_data],
                   capture_output=True, cwd=WORKSPACE)
if r.returncode != 0:
    fail("L1b: provided generator failed when the verifier re-ran it "
         f"(stderr: {r.stderr.decode()[:200]})")
with open(ref_data, "rb") as f:
    ref_bytes = f.read()
with open(os.path.join(WORKSPACE, "data.in"), "rb") as f:
    agent_bytes = f.read()
check(ref_bytes == agent_bytes,
      "L1b: data.in does not match the provided generator's output - "
      "the system was not built by the shipped template script")
os.remove(ref_data)

# ── L2: log integrity (per stage) ────────────────────────────────────────────────

EQ_MIN_ROWS = refs.get("eq_min_thermo_rows", 10)

def log_banner_ok(logpath):
    c = open(logpath).read()
    return ("LAMMPS" in c) and ("Total wall time" in c)

# (log file, target T, exact thermo-row count or None for a min check)
STAGES = [
    ("log.eq_T1", 1.0, None),
    ("log.eq_T04", 0.4, None),
    ("log.T04", 0.4, refs["n_thermo_rows_ref"]),
]
for logp, Ttarget, exact_rows in STAGES:
    path = os.path.join(WORKSPACE, logp)
    check(log_banner_ok(path), f"{logp}: not a complete LAMMPS log")
    logc = open(path).read()
    check(re.search(rf"^\s*{refs['n_atoms_ref']}\s+atoms", logc, re.MULTILINE),
          f"{logp} does not report {refs['n_atoms_ref']} atoms")
    rows = np.array(parse_thermo(path))
    if exact_rows is not None:
        check(len(rows) == exact_rows,
              f"{logp} has {len(rows)} thermo rows (expected {exact_rows})")
    else:
        check(len(rows) >= EQ_MIN_ROWS,
              f"{logp} has only {len(rows)} thermo rows (min {EQ_MIN_ROWS})")
    T_avg = rows[:, 1].mean()
    check(abs(T_avg - Ttarget) / Ttarget <= refs["temp_tol_frac"],
          f"{logp} mean T={T_avg:.4f} != target {Ttarget} "
          f"(tol {refs['temp_tol_frac']*100:.0f}%)")
    if logp == "log.T04":
        et = rows[:, 4]
        spread = (et.max() - et.min()) / abs(et.mean())
        check(spread <= refs["etotal_cons_tol_frac"],
              f"log.T04 NVE energy not conserved "
              f"(rel spread {spread:.5f} > {refs['etotal_cons_tol_frac']})")

# ── L2b: data structure of the equilibrated states ──────────────────────────────

for df in ("data_T1.lammps", "data_T04.lammps"):
    path = os.path.join(WORKSPACE, df)
    counts, types, box, has_vel = parse_data(path)
    check(counts.get("atoms") == refs["n_atoms_ref"],
          f"{df}: {counts.get('atoms')} atoms (expected {refs['n_atoms_ref']})")
    check(counts.get("bonds") == refs["n_bonds_ref"],
          f"{df}: {counts.get('bonds')} bonds (expected {refs['n_bonds_ref']})")
    check(counts.get("angles") == refs["n_angles_ref"],
          f"{df}: {counts.get('angles')} angles (expected {refs['n_angles_ref']})")
    n_sticker = types.get(2, 0)
    n_bead = types.get(1, 0)
    check(n_sticker == refs["n_sticker_ref"] and
          n_bead == refs["n_atoms_ref"] - refs["n_sticker_ref"],
          f"{df}: sticker/bead types {n_sticker}/{n_bead} "
          f"(expected {refs['n_sticker_ref']}/{refs['n_atoms_ref'] - refs['n_sticker_ref']})")
    for axis in ("xlo", "ylo", "zlo"):
        lo, hi = box[axis]
        side = hi - lo
        check(abs(side - refs["box_side_ref"]) <= refs["box_side_tol"],
              f"{df}: {axis} side {side:.4f} != {refs['box_side_ref']:.4f} "
              f"(tol {refs['box_side_tol']})")
    check(has_vel, f"{df}: missing Velocities section "
                   "(equilibrated state must carry velocities)")

# ── L3: HCACF structure ──────────────────────────────────────────────────────────

blocks = parse_acf(os.path.join(WORKSPACE, "J0Jt_T04.dat"))
full = [b for b in blocks if len(b) >= NLAGS and b[0][2] >= refs["ncount_lag0_ref"]]
check(len(full) == refs["n_blocks_ref"],
      f"J0Jt_T04.dat has {len(full)} complete blocks (expected {refs['n_blocks_ref']})")
for b in full:
    check(len(b) == NLAGS, f"J0Jt_T04.dat block has {len(b)} lags (expected {NLAGS})")
G0 = sum(full[0][0][3:6])
check(G0 > 0, f"J0Jt_T04.dat G(0) = {G0:.4e} must be positive")

# ── L4 / L5 / L6: kappa ──────────────────────────────────────────────────────────

n_blocks = int(values["n_blocks"])
check(n_blocks == refs["n_blocks_ref"],
      f"results.json n_blocks={n_blocks} != expected {refs['n_blocks_ref']}")

k = float(values["kappa_T04"])
err = float(values["kappa_err_T04"])
check(err > 0, "kappa_err_T04 must be positive")
check(err < k, f"kappa_err_T04={err:.5f} >= kappa_T04={k:.5f} - implausible error bar")

ref = refs["kappa_T04_ref"]
check(abs(k - ref) / abs(ref) <= refs["kappa_tol_frac"],
      f"kappa_T04={k:.6f} differs from ref {ref:.6f} by "
      f">{refs['kappa_tol_frac']*100:.0f}%")

# Layer 5: verifier re-derives kappa from the J0Jt file
G, n = avg_acf(blocks)
k_refit, _ = kappa_from_G(G, refs["vol_T04"], TARGET_T04)
check(abs(k_refit - k) / abs(k) <= refs["consistency_kappa_tol_frac"],
      f"kappa_T04={k:.6f} != verifier refit of the J0Jt ACF {k_refit:.6f} "
      f"(tol {refs['consistency_kappa_tol_frac']*100:.0f}%)")

# Layer 6 (real recompute): kappa from the raw heat-flux series
_, jx, jy, jz = parse_flux(os.path.join(WORKSPACE, "flux_T04.dat"))
check(len(jx) >= refs["n_flux_rows_min"],
      f"flux_T04.dat has only {len(jx)} samples (expected >= {refs['n_flux_rows_min']})")
nraw = len(jx)
Graw = np.zeros(NLAGS)
for lag in range(NLAGS):
    Graw[lag] = np.mean(jx[:nraw - lag] * jx[lag:] +
                        jy[:nraw - lag] * jy[lag:] +
                        jz[:nraw - lag] * jz[lag:])
k_rec, _ = kappa_from_G(Graw, refs["vol_T04"], TARGET_T04)
check(abs(k_rec - k) / abs(k) <= refs["l6_kappa_tol_frac"],
      f"L6: kappa_T04 recomputed from the raw flux series = {k_rec:.6f} "
      f"!= results.json {k:.6f} (tol {refs['l6_kappa_tol_frac']*100:.0f}%) - "
      f"the flux series does not back the reported kappa")
check(abs(Graw[0] - G[0]) / abs(G[0]) <= refs["l6_G0_tol_frac"],
      f"L6: raw-series <J^2> = {Graw[0]:.4e} != J0Jt G(0) = {G[0]:.4e} "
      f"(tol {refs['l6_G0_tol_frac']*100:.0f}%)")

print("PASS: lammps-thermal-conductivity")

#!/usr/bin/env python3
"""
Verifier for lammps-thermal-conductivity.

Layers:
  1. File existence + results.json values/units schema
  2. Log integrity: LAMMPS banner, run completion, atom count, thermo row count,
     mean temperature vs the state point, NVE energy conservation
  3. HCACF structure: block markers, 200 lags per block, exactly 8 complete
     blocks, lag-0 Ncount, positive G(0)
  4. Numerical tolerance: kappa_T1 / kappa_T04 within tolerance of the
     calibrated reference
  5. Consistency: the verifier re-derives kappa from the J0Jt files with the
     reference protocol - must match results.json
  6. L4 REAL RECOMPUTE: the verifier computes the heat-flux autocorrelation
     from the raw flux_*.dat time series and integrates it again; requires the
     recomputed kappa to match results.json and the lag-0 <J^2> to match the
     J0Jt files. A fabricated ACF backed by an inconsistent flux series fails here.
"""
import json
import sys
import os
import re

import numpy as np

WORKSPACE = os.environ.get("GK_WORKSPACE", "/workspace")
REFS_PATH = os.environ.get("GK_REFS", "/tests/refs.json")

DT = 0.005
NEVERY = 5
DT_DATA = NEVERY * DT          # lag spacing in tau
KBT = 1.0
WINDOW = 10
NLAGS = 200
SUFFIXES = ["T1", "T04"]
TARGET = {"T1": 1.0, "T04": 0.4}


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


# ── Layer 1: existence + schema ──────────────────────────────────────────────────

for fname in ("results.json", "log.T1", "log.T04",
              "J0Jt_T1.dat", "J0Jt_T04.dat", "flux_T1.dat", "flux_T04.dat"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("kappa_T1", "kappa_T04", "kappa_err_T1", "kappa_err_T04", "n_blocks"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: log integrity (per state point) ────────────────────────────────────

for s in SUFFIXES:
    logpath = os.path.join(WORKSPACE, f"log.{s}")
    logc = open(logpath).read()
    check("LAMMPS" in logc, f"log.{s} missing LAMMPS banner")
    check("Total wall time" in logc, f"log.{s} missing 'Total wall time' - run incomplete")
    check(re.search(rf"^\s*{refs['n_atoms_ref']}\s+atoms", logc, re.MULTILINE),
          f"log.{s} does not report {refs['n_atoms_ref']} atoms")
    rows = []
    seg = False
    for line in logc.splitlines():
        t = line.strip()
        if re.match(r"^Step\s+", t, re.IGNORECASE):
            seg = True
            continue
        if seg:
            if "Loop time" in line:
                break
            if re.match(r"^\d+\s+", t):
                p = t.split()
                try:
                    rows.append([float(x) for x in p])
                except ValueError:
                    pass
    check(len(rows) == refs["n_thermo_rows_ref"],
          f"log.{s} has {len(rows)} thermo rows (expected {refs['n_thermo_rows_ref']})")
    rows = np.array(rows)
    T_avg = rows[:, 1].mean()
    check(abs(T_avg - TARGET[s]) / TARGET[s] <= refs["temp_tol_frac"],
          f"log.{s} mean T={T_avg:.4f} != target {TARGET[s]} (tol {refs['temp_tol_frac']*100:.0f}%)")
    et = rows[:, 4]
    spread = (et.max() - et.min()) / abs(et.mean())
    check(spread <= refs["etotal_cons_tol_frac"],
          f"log.{s} NVE energy not conserved (rel spread {spread:.5f} > {refs['etotal_cons_tol_frac']})")

# ── Layer 3: HCACF structure (per state point) ─────────────────────────────────

for s in SUFFIXES:
    blocks = parse_acf(os.path.join(WORKSPACE, f"J0Jt_{s}.dat"))
    full = [b for b in blocks if len(b) >= NLAGS and b[0][2] >= refs["ncount_lag0_ref"]]
    check(len(full) == refs["n_blocks_ref"],
          f"J0Jt_{s}.dat has {len(full)} complete blocks (expected {refs['n_blocks_ref']})")
    for b in full:
        check(len(b) == NLAGS, f"J0Jt_{s}.dat block has {len(b)} lags (expected {NLAGS})")
    G0 = sum(full[0][0][3:6])
    check(G0 > 0, f"J0Jt_{s}.dat G(0) = {G0:.4e} must be positive")

# ── Layers 4, 5, 6 (per state point) ────────────────────────────────────────────

n_blocks = int(values["n_blocks"])
check(n_blocks == refs["n_blocks_ref"],
      f"results.json n_blocks={n_blocks} != expected {refs['n_blocks_ref']}")

for s in SUFFIXES:
    k = float(values[f"kappa_{s}"])
    err = float(values[f"kappa_err_{s}"])
    check(err > 0, f"kappa_err_{s} must be positive")
    check(err < k, f"kappa_err_{s}={err:.5f} >= kappa_{s}={k:.5f} - implausible error bar")

    ref = refs[f"kappa_{s}_ref"]
    check(abs(k - ref) / abs(ref) <= refs["kappa_tol_frac"],
          f"kappa_{s}={k:.6f} differs from ref {ref:.6f} by "
          f">{refs['kappa_tol_frac']*100:.0f}%")

    # Layer 5: verifier re-derives kappa from the J0Jt files
    G, n = avg_acf(parse_acf(os.path.join(WORKSPACE, f"J0Jt_{s}.dat")))
    k_refit, _ = kappa_from_G(G, refs[f"vol_{s}"], TARGET[s])
    check(abs(k_refit - k) / abs(k) <= refs["consistency_kappa_tol_frac"],
          f"kappa_{s}={k:.6f} != verifier refit of the J0Jt ACF {k_refit:.6f} "
          f"(tol {refs['consistency_kappa_tol_frac']*100:.0f}%)")

    # Layer 6 (L4 real recompute): kappa from the raw heat-flux series
    _, jx, jy, jz = parse_flux(os.path.join(WORKSPACE, f"flux_{s}.dat"))
    check(len(jx) >= refs["n_flux_rows_min"],
          f"flux_{s}.dat has only {len(jx)} samples (expected >= {refs['n_flux_rows_min']})")
    nraw = len(jx)
    Graw = np.zeros(NLAGS)
    for lag in range(NLAGS):
        Graw[lag] = np.mean(jx[:nraw - lag] * jx[lag:] +
                            jy[:nraw - lag] * jy[lag:] +
                            jz[:nraw - lag] * jz[lag:])
    k_rec, _ = kappa_from_G(Graw, refs[f"vol_{s}"], TARGET[s])
    check(abs(k_rec - k) / abs(k) <= refs["l6_kappa_tol_frac"],
          f"L6: kappa_{s} recomputed from the raw flux series = {k_rec:.6f} "
          f"!= results.json {k:.6f} (tol {refs['l6_kappa_tol_frac']*100:.0f}%) - "
          f"the flux series does not back the reported kappa")
    check(abs(Graw[0] - G[0]) / abs(G[0]) <= refs["l6_G0_tol_frac"],
          f"L6: raw-series <J^2> = {Graw[0]:.4e} != J0Jt G(0) = {G[0]:.4e} "
          f"(tol {refs['l6_G0_tol_frac']*100:.0f}%)")

print("PASS: lammps-thermal-conductivity")

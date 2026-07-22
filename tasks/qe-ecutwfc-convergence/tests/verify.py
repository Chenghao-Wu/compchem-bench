#!/usr/bin/env python3
"""
Verifier for qe-ecutwfc-convergence:
  1. File existence (5 cutoff logs + results.json schema)
  2. Asset integrity: sha256 of the Si pseudopotential (used by the L4
     recompute) BEFORE any use
  3. Per-log integrity: PWSCF v7.4 banner, SCF iteration table, convergence,
     JOB DONE., and settings echoes matching the task (ecutwfc = the file's
     cutoff, ecutrho = 480 Ry, 10 irreducible k-points, 2 atoms)
  4. log <-> results.json consistency per cutoff
  5. Numerical tolerance vs calibrated x86_64 references (per cutoff)
  6. Criterion derivation: re-derive the converged cutoff from the agent's
     own energy table (1 meV/atom rule) and require it to match both the
     reported value and the reference
  7. REAL RECOMPUTE (L4): the verifier re-runs the lowest-cutoff point
     (ecutwfc=20) itself and requires agreement with the agent's log and
     results.json. Any recompute failure is a hard fail.
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
RY_PER_HA = 2.0
MEV_IN_RY = 1e-3 / 13.605693122
GRID = [20, 30, 40, 50, 60]


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ──────────────────────────────────────────
res_path = os.path.join(WORKSPACE, "results.json")
check(os.path.isfile(res_path), "Missing: results.json")
with open(res_path) as f:
    results = json.load(f)
check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]
for key in ("ecutwfc_grid", "total_energies", "converged_ecutwfc", "criterion_meV_per_atom"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

check([float(x) for x in values["ecutwfc_grid"]] == [float(g) for g in GRID],
      f"ecutwfc_grid must be {GRID}, got {values['ecutwfc_grid']}")
energies_rep = values["total_energies"]
check(isinstance(energies_rep, list) and len(energies_rep) == len(GRID),
      f"total_energies must have {len(GRID)} entries")
energies_rep = [float(e) for e in energies_rep]

# ── Layer 2: Asset integrity (before any use of assets) ──────────────────────
for rel, want in refs["asset_hashes"].items():
    p = os.path.join(WORKSPACE, rel)
    check(os.path.isfile(p), f"Missing asset required for verification: {rel}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    check(got == want, f"Asset {rel} sha256 mismatch (tampered?): {got} != {want}")

# ── Layer 3: Per-log integrity ────────────────────────────────────────────────
log_energies = {}
for ecut in GRID:
    out_path = os.path.join(WORKSPACE, f"si_ecut{ecut}.out")
    check(os.path.isfile(out_path), f"Missing: si_ecut{ecut}.out")
    with open(out_path) as f:
        content = f.read()
    check(re.search(r"Program PWSCF v\.7\.4", content),
          f"si_ecut{ecut}.out missing 'Program PWSCF v.7.4' version banner")
    check("JOB DONE." in content,
          f"si_ecut{ecut}.out missing 'JOB DONE.' — run did not finish cleanly")
    iters = re.findall(r"iteration #\s*\d+", content)
    check(len(iters) >= 3,
          f"si_ecut{ecut}.out: SCF iteration table too short ({len(iters)}) — not a real pw.x log")
    check("convergence has been achieved" in content,
          f"si_ecut{ecut}.out: missing 'convergence has been achieved'")
    check(re.search(rf"kinetic-energy cutoff\s*=\s*{ecut}\.0000\s+Ry", content),
          f"si_ecut{ecut}.out: ecutwfc echo is not {ecut}.0000 Ry — wrong settings")
    check(re.search(r"charge density cutoff\s*=\s*480\.0000\s+Ry", content),
          f"si_ecut{ecut}.out: ecutrho echo is not 480.0000 Ry — ecutrho must stay fixed")
    m = re.search(r"number of k points=\s*(\d+)", content)
    check(m and int(m.group(1)) == 10,
          f"si_ecut{ecut}.out: expected 10 irreducible k-points, found {m.group(1) if m else 'none'}")
    m = re.search(r"number of atoms/cell\s*=\s*([\d.]+)", content)
    check(m and abs(float(m.group(1)) - 2.0) < 1e-6,
          f"si_ecut{ecut}.out: expected 2 atoms/cell")
    es = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    check(es, f"si_ecut{ecut}.out: no '! total energy' line")
    log_energies[ecut] = float(es[-1])

# ── Layer 4: log <-> results consistency ─────────────────────────────────────
for i, ecut in enumerate(GRID):
    check(abs(log_energies[ecut] - energies_rep[i]) <= refs["consistency_energy_tol_Ry"],
          f"results.json energy at ecut={ecut} ({energies_rep[i]:.8f}) != log "
          f"({log_energies[ecut]:.8f}) Ry")

# ── Layer 5: Reference tolerance ──────────────────────────────────────────────
for i, ecut in enumerate(GRID):
    ref = refs["energy_Ry_ref"][str(ecut)]
    tol = refs["energy_Ry_tol"]
    check(abs(energies_rep[i] - ref) <= tol,
          f"energy at ecut={ecut}: {energies_rep[i]:.8f} Ry differs from ref "
          f"{ref:.8f} Ry by >{tol:.2e}")

# ── Layer 6: Criterion derivation ────────────────────────────────────────────
check(abs(float(values["criterion_meV_per_atom"]) - 1.0) < 1e-6,
      "criterion_meV_per_atom must be 1.0")
nat = 2
converged_derived = None
for i in range(1, len(GRID)):
    delta = abs(energies_rep[i] - energies_rep[i - 1]) / nat
    if delta < 1.0 * MEV_IN_RY:
        converged_derived = float(GRID[i])
        break
check(converged_derived is not None,
      "The agent's own energy table shows no convergence below 1 meV/atom — wrong data")
rep_conv = float(values["converged_ecutwfc"])
check(rep_conv == converged_derived,
      f"converged_ecutwfc={rep_conv} does not follow from the reported table "
      f"(derivation gives {converged_derived})")
check(rep_conv == refs["converged_ecutwfc_ref"],
      f"converged_ecutwfc={rep_conv} != reference {refs['converged_ecutwfc_ref']}")

# ── Layer 7: REAL RECOMPUTE (L4) — re-run the lowest-cutoff point ────────────
sp_input = f"""&CONTROL
  calculation = 'scf'
  prefix = 'crossverify'
  outdir = './cv_outdir'
  pseudo_dir = '{ASSETS}/pseudo'
/
&SYSTEM
  ibrav = 2
  celldm(1) = 10.26
  nat = 2
  ntyp = 1
  ecutwfc = 20.0
  ecutrho = 480.0
/
&ELECTRONS
  conv_thr = 1.0d-10
  mixing_beta = 0.7
/
ATOMIC_SPECIES
  Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS alat
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  4 4 4 1 1 1
"""
tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "cv.in"), "w") as f:
        f.write(sp_input)
    proc = subprocess.run(
        ["pw.x", "-in", "cv.in"], cwd=tmpdir,
        capture_output=True, text=True, timeout=300,
    )
    cv_out = proc.stdout + proc.stderr
    check(proc.returncode == 0 and "JOB DONE." in cv_out,
          f"Cross-verify recompute: pw.x failed (rc={proc.returncode})\n{cv_out[-2000:]}")
    m_re = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", cv_out)
    check(m_re, "Cross-verify recompute: no total energy in pw.x output")
    energy_re = float(m_re[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Ry"]
check(abs(energy_re - log_energies[20]) <= cv_tol,
      f"Cross-verify: recomputed {energy_re:.8f} Ry != agent log "
      f"{log_energies[20]:.8f} Ry (tol {cv_tol:.1e}) — the ecut=20 log is not a real run")
check(abs(energy_re - energies_rep[0]) <= cv_tol,
      f"Cross-verify: recomputed {energy_re:.8f} Ry != results.json "
      f"{energies_rep[0]:.8f} Ry (tol {cv_tol:.1e})")

print("PASS: qe-ecutwfc-convergence")

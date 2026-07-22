#!/usr/bin/env python3
"""
Verifier for xtb-freq-thermo:
  1. File existence + results.json schema (values/units)
  2. Output integrity (xtb banner, GEOMETRY OPTIMIZATION CONVERGED,
     zero imaginary frequencies, normal termination)
  3. results.json sanity (n_imaginary_freqs == 0)
  4. log <-> results consistency (thermochemistry summary block)
  5. Numerical tolerance vs calibrated refs (energy, ZPE, G)
  6. Frequency-table integrity (vibspectrum: 3N modes, first 6 ~ 0,
     3N-6 genuine modes positive) + INDEPENDENT ZPE RE-derivation from
     the agent's frequency table (must match reported ZPE — thermo
     self-consistency)
  7. REAL RECOMPUTE (cross-verify): GFN2 single point on the agent's
     optimized geometry; requires three-way agreement:
         energy(agent log) == energy(results.json) == energy(recompute)
     Missing/abnormal files or any recompute failure is a hard fail —
     there is no skip/warning path.
"""
import json
import sys
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"

# 1 cm^-1 in Hartree (CODATA 2018, hc in Eh)
CM1_TO_EH = 4.556335252912e-6


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def parse_xyz(path):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    natoms = int(lines[0])
    atoms = []
    for line in lines[2:2 + natoms]:
        p = line.split()
        atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))
    return atoms


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Layer 1: File existence + schema ───────────────────────────────────────────
for fname in ("xtb_thermo.out", "xtbopt.xyz", "vibspectrum", "results.json"):
    check(os.path.isfile(os.path.join(WORKSPACE, fname)), f"Missing: {fname}")

with open(os.path.join(WORKSPACE, "results.json")) as f:
    results = json.load(f)

check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for key in ("total_energy", "zpe", "free_energy_298", "n_imaginary_freqs"):
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")

# ── Layer 2: Output integrity ──────────────────────────────────────────────────
with open(os.path.join(WORKSPACE, "xtb_thermo.out")) as f:
    content = f.read()

check("x T B" in content or "xtb version" in content,
      "xtb_thermo.out missing xtb banner")
check("GEOMETRY OPTIMIZATION CONVERGED" in content,
      "xtb_thermo.out: optimization did not converge")
check("normal termination of xtb" in content,
      "xtb_thermo.out missing 'normal termination of xtb'")


def grab(pattern, name):
    m = re.findall(pattern, content)
    check(m, f"No {name} found in xtb_thermo.out")
    return float(m[-1])


energy_log = grab(r"::\s*total energy\s+([-\d.]+)\s+Eh", "total energy")
zpe_log = grab(r"::\s*zero point energy\s+([-\d.]+)\s+Eh", "zero point energy")
free_log = grab(r"::\s*total free energy\s+([-\d.]+)\s+Eh", "total free energy")
n_imag_log = int(grab(r"# imaginary freq\.\s+(\d+)", "imaginary-frequency count"))
check(n_imag_log == 0, f"Log reports {n_imag_log} imaginary frequencies")

# ── Layer 3: results.json sanity ───────────────────────────────────────────────
check(values["n_imaginary_freqs"] == 0, "n_imaginary_freqs must be 0")

# ── Layer 4: log <-> results consistency ───────────────────────────────────────
ctol = refs["consistency_energy_tol_Eh"]
check(abs(energy_log - values["total_energy"]) <= ctol,
      f"results.json total_energy != log ({values['total_energy']:.10f} vs "
      f"{energy_log:.10f}, tol {ctol:.1e})")
check(abs(zpe_log - values["zpe"]) <= ctol,
      f"results.json zpe != log ({values['zpe']:.10f} vs {zpe_log:.10f})")
check(abs(free_log - values["free_energy_298"]) <= ctol,
      f"results.json free_energy_298 != log ({values['free_energy_298']:.10f} "
      f"vs {free_log:.10f})")

# ── Layer 5: Reference tolerance ───────────────────────────────────────────────
check(abs(energy_log - refs["total_energy_Eh_ref"]) <= refs["total_energy_Eh_tol"],
      f"total_energy={energy_log:.10f} Eh differs from ref "
      f"{refs['total_energy_Eh_ref']:.10f} Eh by >{refs['total_energy_Eh_tol']:.1e}")
check(abs(zpe_log - refs["zpe_Eh_ref"]) <= refs["zpe_Eh_tol"],
      f"zpe={zpe_log:.10f} Eh differs from ref {refs['zpe_Eh_ref']:.10f} Eh "
      f"by >{refs['zpe_Eh_tol']:.1e}")
check(abs(free_log - refs["free_energy_298_Eh_ref"]) <= refs["free_energy_298_Eh_tol"],
      f"free_energy_298={free_log:.10f} Eh differs from ref "
      f"{refs['free_energy_298_Eh_ref']:.10f} Eh by >{refs['free_energy_298_Eh_tol']:.1e}")

# ── Layer 6: Frequency-table integrity + independent ZPE re-derivation ────────
atoms = parse_xyz(os.path.join(WORKSPACE, "xtbopt.xyz"))
n_atoms = len(atoms)
check(n_atoms == 9, f"xtbopt.xyz has {n_atoms} atoms (expected 9: ethanol)")
counts = Counter(a[0] for a in atoms)
check(counts == Counter({"C": 2, "H": 6, "O": 1}),
      f"xtbopt.xyz composition {dict(counts)} != ethanol C2H6O")

freqs = []
with open(os.path.join(WORKSPACE, "vibspectrum")) as f:
    for line in f:
        s = line.strip()
        if not s or s.startswith("$") or s.startswith("#"):
            continue
        p = s.split()
        if len(p) >= 3 and re.match(r"^\d+$", p[0]):
            try:
                freqs.append(float(p[2]))
            except ValueError:
                pass

check(len(freqs) == 3 * n_atoms,
      f"vibspectrum lists {len(freqs)} modes; expected 3N = {3 * n_atoms}")

tr = freqs[:6]
real = freqs[6:]
check(all(abs(f) <= refs["tr_mode_absmax_cm1"] for f in tr),
      f"First 6 (translation/rotation) modes not ~0: {tr}")
check(all(f > refs["min_real_freq_cm1"] for f in real),
      f"Found non-positive/tiny genuine vibrational modes "
      f"(min {min(real):.2f} cm^-1 <= {refs['min_real_freq_cm1']} cm^-1)")

# Independent ZPE re-derivation from the agent's frequency table:
#   ZPE = 1/2 * sum(hc * wavenumber) over the 3N-6 genuine modes
zpe_re = 0.5 * sum(real) * CM1_TO_EH
zpe_tol = refs["zpe_recompute_tol_Eh"]
check(abs(zpe_re - zpe_log) <= zpe_tol,
      f"ZPE re-derived from vibspectrum ({zpe_re:.8f} Eh) != log ZPE "
      f"({zpe_log:.8f} Eh, tol {zpe_tol:.1e}) — thermochemistry not "
      f"self-consistent with the frequency table")
check(abs(zpe_re - values["zpe"]) <= zpe_tol,
      f"ZPE re-derived from vibspectrum ({zpe_re:.8f} Eh) != results.json "
      f"({values['zpe']:.8f} Eh, tol {zpe_tol:.1e})")

# ── Layer 7: REAL RECOMPUTE — single point on the agent's optimized geometry ──
xyz_lines = [str(n_atoms), "crossverify single point"]
for sym, x, y, z in atoms:
    xyz_lines.append(f"{sym:2s}  {x:.10f}  {y:.10f}  {z:.10f}")

tmpdir = tempfile.mkdtemp(prefix="crossverify_")
try:
    with open(os.path.join(tmpdir, "mol.xyz"), "w") as f:
        f.write("\n".join(xyz_lines) + "\n")
    env = dict(os.environ, OMP_NUM_THREADS="1")
    proc = subprocess.run(
        ["xtb", "mol.xyz", "--gfn", "2"],
        cwd=tmpdir, env=env, capture_output=True, text=True, timeout=300,
    )
    check(proc.returncode == 0,
          f"Cross-verify recompute: xtb exited with code {proc.returncode}\n"
          f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    check("normal termination of xtb" in proc.stdout + proc.stderr,
          "Cross-verify recompute: xtb did not terminate normally")
    m = re.findall(r"TOTAL ENERGY\s+([-\d.]+)\s+Eh", proc.stdout)
    check(m, "Cross-verify recompute: no TOTAL ENERGY in xtb output")
    energy_re = float(m[-1])
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

cv_tol = refs["crossverify_energy_tol_Eh"]
check(
    abs(energy_re - energy_log) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.12f} Eh != agent log {energy_log:.12f} Eh "
    f"(tol {cv_tol:.1e}) — log does not correspond to the optimized geometry",
)
check(
    abs(energy_re - values["total_energy"]) <= cv_tol,
    f"Cross-verify: recomputed {energy_re:.12f} Eh != results.json "
    f"{values['total_energy']:.12f} Eh (tol {cv_tol:.1e})",
)

print("PASS: xtb-freq-thermo")

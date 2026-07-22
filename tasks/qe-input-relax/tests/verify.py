#!/usr/bin/env python3
"""
Verifier for qe-input-relax:
  1. File existence (sic_vc_relax.in)
  2. QE input parses (namelists + cards)
  3. Semantic requirements: calculation='vc-relax', conv_thr <= 1e-8,
     forc_conv_thr <= 1e-4, ecutwfc >= 40 Ry, automatic MP k-grid >= 4x4x4,
     nat=2 / ntyp=2 with species {Si, C}
  4. Structure: the deck encodes the zinc-blende SiC primitive cell
     (a = 4.3596 Ang, Si at (0,0,0), C at (1/4,1/4,1/4) crystal) — any valid
     cell/position spelling accepted; cell metric compared to reference
  5. Pseudopotential integrity: the UPF files the deck references exist and
     are sha256-identical to the provided assets (asset_hashes)
  6. L4-LITE REAL RUN: the verifier truncates the agent's exact deck to a
     single-point (calculation='scf', everything else preserved) and runs it
     with the in-image pw.x — the run must reach 'convergence has been
     achieved' + 'JOB DONE.'. Any input error pw.x rejects is a hard fail.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

WORKSPACE = "/workspace"
REFS_PATH = "/tests/refs.json"
BOHR_PER_ANG = 1.0 / 0.529177210903


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


with open(REFS_PATH) as f:
    refs = json.load(f)

# ── Minimal QE input parser ───────────────────────────────────────────────────
def parse_qe_input(text):
    """Parse a pw.x input into {'namelists': {name: {key: val}}, 'cards': ...}.
    Values: quoted strings -> str, Fortran numbers -> float, .true./.false. -> bool.
    """
    lines = []
    for raw in text.splitlines():
        # strip comments ('!' outside quotes)
        line, in_q = "", False
        for ch in raw:
            if ch in "'\"":
                in_q = not in_q
            if ch == "!" and not in_q:
                break
            line += ch
        lines.append(line.rstrip())

    namelists = {}
    cards = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"&(\w+)", line, re.IGNORECASE)
        if m:
            name = m.group(1).lower()
            body = line[m.end():]
            i += 1
            while i < len(lines) and lines[i].strip() != "/":
                body += "\n" + lines[i]
                i += 1
            i += 1  # skip '/'
            entries = {}
            # split on commas not inside quotes, or newlines
            body = re.sub(r",\s*(?=\w+\s*[\(,]?\s*=)", "\n", body)
            for part in body.splitlines():
                part = part.strip().rstrip(",")
                if not part or "=" not in part:
                    continue
                k, v = part.split("=", 1)
                k = k.strip().lower()
                v = v.strip().strip(",")
                if len(v) >= 2 and v[0] in "'\"" and v[-1] in "'\"":
                    val = v[1:-1]
                elif v.lower() in (".true.", "true"):
                    val = True
                elif v.lower() in (".false.", "false"):
                    val = False
                else:
                    try:
                        val = float(v.replace("d", "e").replace("D", "E"))
                    except ValueError:
                        val = v
                entries[k] = val
            namelists[name] = entries
            continue
        m = re.match(r"(ATOMIC_SPECIES|ATOMIC_POSITIONS|K_POINTS|CELL_PARAMETERS)\b(.*)", line, re.IGNORECASE)
        if m:
            cname = m.group(1).upper()
            copt = m.group(2).strip()
            i += 1
            body = []
            while i < len(lines):
                nxt = lines[i].strip()
                if re.match(r"&\w+", nxt) or re.match(
                        r"(ATOMIC_SPECIES|ATOMIC_POSITIONS|K_POINTS|CELL_PARAMETERS|OCCUPATIONS|CONSTRAINTS|ATOMIC_FORCES)\b",
                        nxt, re.IGNORECASE) or nxt == "" and body and len(body) > 0 and False:
                    break
                body.append(lines[i])
                i += 1
            cards[cname] = {"option": copt, "lines": [l for l in body if l.strip()]}
            continue
        i += 1
    return {"namelists": namelists, "cards": cards}


def num(namelist, key, default=None):
    v = namelist.get(key, default)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ── Layer 1: File existence ───────────────────────────────────────────────────
in_path = os.path.join(WORKSPACE, "sic_vc_relax.in")
check(os.path.isfile(in_path), "Missing: sic_vc_relax.in")
with open(in_path) as f:
    deck_text = f.read()

# ── Layer 2: Parse ────────────────────────────────────────────────────────────
try:
    deck = parse_qe_input(deck_text)
except Exception as e:
    fail(f"sic_vc_relax.in does not parse as a QE input: {e}")
namelists, cards = deck["namelists"], deck["cards"]
for nl in ("control", "system"):
    check(nl in namelists, f"sic_vc_relax.in missing &{nl.upper()} namelist")
control, system = namelists["control"], namelists["system"]
for card in ("ATOMIC_SPECIES", "ATOMIC_POSITIONS", "K_POINTS"):
    check(card in cards, f"sic_vc_relax.in missing {card} card")

# ── Layer 3: Semantic requirements ───────────────────────────────────────────
calc = str(control.get("calculation", "")).lower()
check(calc == "vc-relax", f"calculation must be 'vc-relax', got {calc!r}")

conv_thr = num(namelists.get("electrons", {}), "conv_thr")
check(conv_thr is not None, "conv_thr not set in &ELECTRONS")
check(conv_thr <= refs["conv_thr_max"],
      f"conv_thr={conv_thr:g} exceeds required {refs['conv_thr_max']:g}")

forc_conv_thr = num(control, "forc_conv_thr")
check(forc_conv_thr is not None, "forc_conv_thr not set in &CONTROL")
check(forc_conv_thr <= refs["forc_conv_thr_max"],
      f"forc_conv_thr={forc_conv_thr:g} exceeds required {refs['forc_conv_thr_max']:g}")

ecutwfc = num(system, "ecutwfc")
check(ecutwfc is not None, "ecutwfc not set in &SYSTEM")
check(ecutwfc >= refs["ecutwfc_min_Ry"],
      f"ecutwfc={ecutwfc:g} below required {refs['ecutwfc_min_Ry']:g} Ry")

kp = cards["K_POINTS"]
check(re.match(r"automatic", kp["option"], re.IGNORECASE),
      f"K_POINTS must be 'automatic' (got option {kp['option']!r})")
check(len(kp["lines"]) >= 1, "K_POINTS automatic mesh line missing")
mesh = kp["lines"][0].split()
check(len(mesh) >= 3, f"K_POINTS automatic line must give 3 mesh integers, got {mesh}")
try:
    n1, n2, n3 = (int(mesh[0]), int(mesh[1]), int(mesh[2]))
except ValueError:
    fail(f"K_POINTS mesh not integers: {mesh[:3]}")
kmin = refs["kgrid_min"]
check(n1 >= kmin and n2 >= kmin and n3 >= kmin,
      f"k-grid {n1}x{n2}x{n3} below required {kmin}x{kmin}x{kmin}")

nat = num(system, "nat")
ntyp = num(system, "ntyp")
check(nat == 2, f"nat must be 2 (primitive cell), got {nat}")
check(ntyp == 2, f"ntyp must be 2, got {ntyp}")

species_lines = cards["ATOMIC_SPECIES"]["lines"]
check(len(species_lines) == 2, f"ATOMIC_SPECIES must list 2 species, got {len(species_lines)}")
species = {}
for l in species_lines:
    p = l.split()
    check(len(p) >= 3, f"malformed ATOMIC_SPECIES line: {l!r}")
    species[p[0]] = {"mass": p[1], "pseudo": p[2]}
check(set(species) == {"Si", "C"}, f"species must be Si and C, got {sorted(species)}")

# ── Layer 4: Structure ────────────────────────────────────────────────────────
ibrav = num(system, "ibrav")
check(ibrav is not None, "ibrav not set in &SYSTEM")
ibrav = int(ibrav)


def cell_from_deck():
    if ibrav == 2:
        celldm1 = num(system, "celldm(1)")
        a_ang = None
        if celldm1:
            a_ang = celldm1 / BOHR_PER_ANG
        elif num(system, "a"):
            a_ang = num(system, "a")
        check(a_ang, "ibrav=2 requires celldm(1) or A")
        h = a_ang / 2.0
        return [[-h, 0.0, h], [0.0, h, h], [-h, h, 0.0]], a_ang
    if ibrav == 0:
        check("CELL_PARAMETERS" in cards, "ibrav=0 requires CELL_PARAMETERS")
        cp = cards["CELL_PARAMETERS"]
        check(len(cp["lines"]) >= 3, "CELL_PARAMETERS must have 3 rows")
        rows = [[float(x) for x in cp["lines"][i].split()[:3]] for i in range(3)]
        opt = cp["option"].lower()
        if "angstrom" in opt:
            scale = 1.0
        elif "bohr" in opt:
            scale = 1.0 / BOHR_PER_ANG
        else:  # alat (default)
            celldm1 = num(system, "celldm(1)")
            a_ang = celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a")
            check(a_ang, "CELL_PARAMETERS alat requires celldm(1) or A")
            scale = a_ang
        return [[x * scale for x in r] for r in rows], None
    fail(f"ibrav={ibrav} not supported for this task (use ibrav=2 or ibrav=0 + CELL_PARAMETERS)")


cell, a_direct = cell_from_deck()


def matvec_t(m, v):
    # fractional -> cartesian with cell rows as lattice vectors: c = f^T C
    return [sum(f * m[i][j] for i, f in enumerate(v)) for j in range(3)]


def invert3(m):
    a1, a2, a3 = m
    b1 = [a2[1] * a3[2] - a2[2] * a3[1], a2[2] * a3[0] - a2[0] * a3[2], a2[0] * a3[1] - a2[1] * a3[0]]
    b2 = [a3[1] * a1[2] - a3[2] * a1[1], a3[2] * a1[0] - a3[0] * a1[2], a3[0] * a1[1] - a3[1] * a1[0]]
    b3 = [a1[1] * a2[2] - a1[2] * a2[1], a1[2] * a2[0] - a1[0] * a2[2], a1[0] * a2[1] - a1[1] * a2[0]]
    det = sum(a1[i] * b1[i] for i in range(3))
    check(abs(det) > 1e-8, "cell matrix is singular")
    inv = [[b1[j] / det for j in range(3)],
           [b2[j] / det for j in range(3)],
           [b3[j] / det for j in range(3)]]
    return inv, det


inv, det = invert3(cell)

# lattice parameter from cell metric (permutation/rotation invariant)
norms = sorted(math.sqrt(sum(x * x for x in row)) for row in cell)
a_from_cell = norms[0] * math.sqrt(2.0)  # fcc primitive: |v| = a/sqrt(2)
for n in norms:
    check(abs(n * math.sqrt(2.0) - a_from_cell) < 1e-6,
          f"primitive cell vectors have unequal norms {norms} — not the fcc primitive cell")
a_ref = refs["lattice_A_ref"]
check(abs(a_from_cell - a_ref) <= refs["lattice_A_tol"],
      f"lattice constant {a_from_cell:.4f} Ang != ref {a_ref} Ang (tol {refs['lattice_A_tol']})")
# fcc metric: off-diagonal dot products must equal |v|^2 cos(60) = |v|^2/2
d01 = sum(cell[0][i] * cell[1][i] for i in range(3))
d02 = sum(cell[0][i] * cell[2][i] for i in range(3))
d12 = sum(cell[1][i] * cell[2][i] for i in range(3))
for d in (d01, d02, d12):
    check(abs(d - norms[0] ** 2 / 2.0) < 1e-4 * norms[0] ** 2,
          "cell vector angles are not the fcc primitive 60 degrees")

pos_lines = cards["ATOMIC_POSITIONS"]["lines"]
check(len(pos_lines) == 2, f"ATOMIC_POSITIONS must have 2 atoms, got {len(pos_lines)}")
pos_opt = cards["ATOMIC_POSITIONS"]["option"].lower()
atoms = []
for l in pos_lines:
    p = l.split()
    check(len(p) >= 4, f"malformed ATOMIC_POSITIONS line: {l!r}")
    check(p[0] in species, f"ATOMIC_POSITIONS species {p[0]!r} not in ATOMIC_SPECIES")
    atoms.append((p[0], [float(p[1]), float(p[2]), float(p[3])]))


def to_fractional(coords):
    if "crystal" in pos_opt:
        return coords
    if "alat" in pos_opt:
        celldm1 = num(system, "celldm(1)")
        a = celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a")
        check(a, "ATOMIC_POSITIONS alat requires celldm(1) or A")
        cart = [c * a for c in coords]
    elif "bohr" in pos_opt:
        cart = [c / BOHR_PER_ANG for c in coords]
    else:  # angstrom (QE default)
        cart = coords
    return [sum(inv[i][j] * cart[j] for j in range(3)) for i in range(3)]


frac = {el: None for el in ("Si", "C")}
for el, co in atoms:
    frac[el] = to_fractional(co)
check(frac["Si"] is not None and frac["C"] is not None,
      "ATOMIC_POSITIONS must contain one Si and one C")

# translation-invariant comparison: C - Si must equal (1/4,1/4,1/4) mod lattice
delta = [frac["C"][i] - frac["Si"][i] for i in range(3)]
delta = [d - round(d) for d in delta]
expected = (0.25, 0.25, 0.25)
crys_tol = refs["position_crystal_tol"]
for i in range(3):
    check(abs(delta[i] - expected[i]) <= crys_tol,
          f"Si->C crystal offset {tuple(round(x, 4) for x in delta)} != zinc-blende (1/4,1/4,1/4) "
          f"(tol {crys_tol})")

# ── Layer 5: Pseudopotential integrity ───────────────────────────────────────
pseudo_dir = str(control.get("pseudo_dir", "./pseudo"))
if not pseudo_dir.startswith("/"):
    pseudo_dir = os.path.normpath(os.path.join(WORKSPACE, pseudo_dir))
want_hashes = refs["asset_hashes"]
for el, fname in (("Si", "Si.pbe-n-rrkjus_psl.1.0.0.UPF"),
                  ("C", "C.pbe-n-kjpaw_psl.1.0.0.UPF")):
    check(species[el]["pseudo"] == fname,
          f"species {el} must use the provided pseudopotential {fname}, got {species[el]['pseudo']!r}")
    p = os.path.join(pseudo_dir, fname)
    check(os.path.isfile(p), f"pseudopotential file not found: {p}")
    got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
    want = want_hashes[f"assets/pseudo/{fname}"]
    check(got == want,
          f"{fname} sha256 mismatch — not the provided pseudopotential: {got} != {want}")

# ── Layer 6: L4-LITE — truncate the deck to a single point and REALLY run it ─
trunc = deck_text


def replace_namelist_value(text, namelist, key, newline):
    pat = re.compile(r"(&" + namelist + r"\b.*?)(^[ \t]*" + key + r"[ \t]*=[^\n]*$)",
                     re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + "  " + newline, text, count=1)
    # key absent: insert right after the namelist opener
    pat2 = re.compile(r"(^\s*&" + namelist + r"\s*$)", re.IGNORECASE | re.MULTILINE)
    check(pat2.search(text), f"&{namelist.upper()} namelist not found for truncation")
    return pat2.sub(lambda m: m.group(1) + "\n  " + newline, text, count=1)


trunc = replace_namelist_value(trunc, "CONTROL", "calculation", "calculation = 'scf'")
trunc = replace_namelist_value(trunc, "CONTROL", "outdir", "outdir = './cv_outdir'")
trunc = replace_namelist_value(trunc, "CONTROL", "pseudo_dir", f"pseudo_dir = '{pseudo_dir}'")

tmpdir = tempfile.mkdtemp(prefix="l4lite_")
try:
    with open(os.path.join(tmpdir, "cv.in"), "w") as f:
        f.write(trunc)
    proc = subprocess.run(
        ["pw.x", "-in", "cv.in"], cwd=tmpdir,
        capture_output=True, text=True, timeout=refs["l4lite_timeout_sec"],
    )
    run_out = proc.stdout + proc.stderr
    check("Error in routine" not in run_out and proc.returncode == 0,
          "L4-lite: pw.x rejected the input deck (truncated to a single point):\n"
          + "\n".join(run_out.splitlines()[-25:]))
    check("convergence has been achieved" in run_out,
          "L4-lite: the truncated single point did not converge — the deck is not runnable as written")
    check("JOB DONE." in run_out,
          "L4-lite: pw.x did not reach JOB DONE. — the deck is not runnable as written")
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

print("PASS: qe-input-relax")

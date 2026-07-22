#!/usr/bin/env python3
"""
Verifier for qe-error-diagnose:
  For each of the three cases:
    1. Fixed input /workspace/caseN/caseN.in exists and parses
    2. Case-specific sanity (the fix must not alter the system or weaken
       the settings):
         case1 — Si, references the real provided UPF filename; the file in
                 the agent's pseudo_dir is sha256-identical to the asset
         case2 — no ibrav!=0 + CELL_PARAMETERS contradiction; reconstructed
                 cell is the intended fcc cell; species Si
         case3 — species C+O with the intended C-O distance; cell intact
       (all cases: ecutwfc/ecutrho/k-grid/conv_thr unchanged from the
        broken input; pseudopotentials hash-verified)
    3. caseN.out is a genuine converged run: PWSCF v7.4 banner, SCF
       iteration table, 'convergence has been achieved', JOB DONE., and the
       cutoff echoes matching the required settings
    4. results.json energy == log energy
    5. log energy vs calibrated x86_64 reference (tight tolerance) —
       really running the fixed inputs to convergence IS the judgment
"""
import hashlib
import json
import math
import os
import re
import sys

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


def parse_qe_input(text):
    lines = []
    for raw in text.splitlines():
        line, in_q = "", False
        for ch in raw:
            if ch in "'\"":
                in_q = not in_q
            if ch == "!" and not in_q:
                break
            line += ch
        lines.append(line.rstrip())

    namelists, cards = {}, {}
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
            i += 1
            entries = {}
            body = re.sub(r",\s*(?=\w+\s*[\(,]?\s*=)", "\n", body)
            for part in body.splitlines():
                part = part.strip().rstrip(",")
                if not part or "=" not in part:
                    continue
                k, v = part.split("=", 1)
                k, v = k.strip().lower(), v.strip().strip(",")
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
            cname, copt = m.group(1).upper(), m.group(2).strip()
            i += 1
            body = []
            while i < len(lines):
                nxt = lines[i].strip()
                if re.match(r"&\w+", nxt) or re.match(
                        r"(ATOMIC_SPECIES|ATOMIC_POSITIONS|K_POINTS|CELL_PARAMETERS|OCCUPATIONS)\b",
                        nxt, re.IGNORECASE):
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
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


CASES = {
    1: {"dir": "case1", "ecutwfc": 45.0, "ecutrho": 360.0, "conv_thr": 1e-10,
        "species": ["Si"], "kmin": 4, "asset": "case1_pseudo",
        "upf": {"Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
    2: {"dir": "case2", "ecutwfc": 35.0, "ecutrho": 280.0, "conv_thr": 1e-10,
        "species": ["Si"], "kmin": 4, "asset": "case2_cell",
        "upf": {"Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
    3: {"dir": "case3", "ecutwfc": 50.0, "ecutrho": 400.0, "conv_thr": 1e-9,
        "species": ["C", "O"], "kmin": 1, "asset": "case3_scf",
        "upf": {"C": "C.pbe-n-kjpaw_psl.1.0.0.UPF", "O": "O.pbe-n-kjpaw_psl.1.0.0.UPF"}},
}

log_energy = {}

for n, spec in CASES.items():
    case_dir = os.path.join(WORKSPACE, spec["dir"])
    in_path = os.path.join(case_dir, f"{spec['dir']}.in")
    out_path = os.path.join(case_dir, f"{spec['dir']}.out")

    # ── Layer 1: fixed input exists and parses ───────────────────────────────
    check(os.path.isfile(in_path), f"Missing: {spec['dir']}/{spec['dir']}.in (fixed input)")
    try:
        deck = parse_qe_input(open(in_path).read())
    except Exception as e:
        fail(f"case{n} fixed input does not parse: {e}")
    nls, cards = deck["namelists"], deck["cards"]
    check("control" in nls and "system" in nls, f"case{n}: missing &CONTROL/&SYSTEM")
    control, system = nls["control"], nls["system"]
    for card in ("ATOMIC_SPECIES", "ATOMIC_POSITIONS", "K_POINTS"):
        check(card in cards, f"case{n}: missing {card} card")

    # ── Layer 2: settings not weakened + case-specific sanity ────────────────
    ecutwfc = num(system, "ecutwfc")
    ecutrho = num(system, "ecutrho")
    check(ecutwfc is not None and abs(ecutwfc - spec["ecutwfc"]) < 1e-9,
          f"case{n}: ecutwfc must stay {spec['ecutwfc']:g} Ry, got {ecutwfc}")
    check(ecutrho is not None and abs(ecutrho - spec["ecutrho"]) < 1e-9,
          f"case{n}: ecutrho must stay {spec['ecutrho']:g} Ry, got {ecutrho}")
    conv_thr = num(nls.get("electrons", {}), "conv_thr")
    check(conv_thr is not None and conv_thr <= spec["conv_thr"],
          f"case{n}: conv_thr must stay <= {spec['conv_thr']:g}, got {conv_thr}")

    kp = cards["K_POINTS"]
    if spec["kmin"] > 1:
        check(re.match(r"automatic", kp["option"], re.IGNORECASE),
              f"case{n}: K_POINTS must stay automatic")
        mesh = kp["lines"][0].split()
        check(len(mesh) >= 3 and all(int(x) >= spec["kmin"] for x in mesh[:3]),
              f"case{n}: k-grid {mesh[:3]} below required {spec['kmin']}x{spec['kmin']}x{spec['kmin']}")

    species_lines = cards["ATOMIC_SPECIES"]["lines"]
    species = {}
    for l in species_lines:
        p = l.split()
        check(len(p) >= 3, f"case{n}: malformed ATOMIC_SPECIES line: {l!r}")
        species[p[0]] = p[2]
    check(set(species) == set(spec["species"]),
          f"case{n}: species must be {spec['species']}, got {sorted(species)}")

    # pseudopotential integrity (agent's copies must be the provided files)
    pseudo_dir = str(control.get("pseudo_dir", "./pseudo"))
    if not pseudo_dir.startswith("/"):
        pseudo_dir = os.path.normpath(os.path.join(case_dir, pseudo_dir))
    for el, fname in spec["upf"].items():
        check(species[el] == fname,
              f"case{n}: {el} must use the provided {fname}, got {species[el]!r}")
        p = os.path.join(pseudo_dir, fname)
        check(os.path.isfile(p), f"case{n}: pseudopotential not found: {p}")
        got = "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()
        want = refs["asset_hashes"][f"assets/{spec['asset']}/pseudo/{fname}"]
        check(got == want, f"case{n}: {fname} sha256 mismatch — not the provided file")

    if n == 2:
        # no ibrav!=0 + CELL_PARAMETERS contradiction, and the cell must be
        # the intended fcc Si cell
        ibrav = int(num(system, "ibrav", -1))
        if ibrav != 0:
            check("CELL_PARAMETERS" not in cards,
                  "case2: still contradictory — CELL_PARAMETERS with ibrav != 0")
        if ibrav == 2:
            celldm1 = num(system, "celldm(1)")
            a_ang = celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a")
            check(a_ang, "case2: ibrav=2 requires celldm(1) or A")
        elif ibrav == 0:
            cp = cards["CELL_PARAMETERS"]
            rows = [[float(x) for x in cp["lines"][i].split()[:3]] for i in range(3)]
            opt = cp["option"].lower()
            if "angstrom" in opt:
                scale = 1.0
            elif "bohr" in opt:
                scale = 1.0 / BOHR_PER_ANG
            else:
                celldm1 = num(system, "celldm(1)")
                scale = (celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a"))
                check(scale, "case2: CELL_PARAMETERS alat requires celldm(1) or A")
            norms = sorted(math.sqrt(sum(x * x for x in r)) * scale for r in rows)
            a_ang = norms[0] * math.sqrt(2.0)
            check(all(abs(x * math.sqrt(2.0) - a_ang) < 1e-6 for x in norms),
                  "case2: CELL_PARAMETERS do not form the fcc primitive cell")
        else:
            fail(f"case2: unexpected ibrav={ibrav} (use ibrav=2 or ibrav=0 + CELL_PARAMETERS)")
        check(abs(a_ang - refs["si_lattice_A_ref"]) <= refs["si_lattice_A_tol"],
              f"case2: lattice constant {a_ang:.4f} Ang != intended "
              f"{refs['si_lattice_A_ref']} Ang — the cell must not be altered")

    if n == 3:
        # C-O distance must stay the intended one
        pos = {}
        opt = cards["ATOMIC_POSITIONS"]["option"].lower()
        for l in cards["ATOMIC_POSITIONS"]["lines"]:
            p = l.split()
            check(len(p) >= 4 and p[0] in species, f"case3: malformed ATOMIC_POSITIONS line: {l!r}")
            xyz = [float(p[1]), float(p[2]), float(p[3])]
            if "alat" in opt:
                celldm1 = num(system, "celldm(1)")
                a = celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a")
                xyz = [c * a for c in xyz]
            elif "bohr" in opt:
                xyz = [c / BOHR_PER_ANG for c in xyz]
            elif "crystal" in opt:
                celldm1 = num(system, "celldm(1)")
                a = celldm1 / BOHR_PER_ANG if celldm1 else num(system, "a")
                xyz = [c * a for c in xyz]
            pos[p[0]] = xyz
        d = math.dist(pos["C"], pos["O"])
        check(abs(d - refs["co_distance_A_ref"]) <= refs["co_distance_A_tol"],
              f"case3: C-O distance {d:.4f} Ang != intended "
              f"{refs['co_distance_A_ref']} Ang — the molecule must not be altered")

    # ── Layer 3: the fixed run really converged ──────────────────────────────
    check(os.path.isfile(out_path), f"Missing: {spec['dir']}/{spec['dir']}.out (fixed run log)")
    content = open(out_path).read()
    check(re.search(r"Program PWSCF v\.7\.4", content),
          f"case{n}: log missing 'Program PWSCF v.7.4' banner")
    check("JOB DONE." in content, f"case{n}: log missing 'JOB DONE.' — run did not finish")
    iters = re.findall(r"iteration #\s*\d+", content)
    check(len(iters) >= 3,
          f"case{n}: SCF iteration table too short ({len(iters)}) — not a real pw.x log")
    check("convergence has been achieved" in content,
          f"case{n}: missing 'convergence has been achieved' — SCF still not converging")
    check(re.search(rf"kinetic-energy cutoff\s*=\s*{spec['ecutwfc']:.4f}\s+Ry", content),
          f"case{n}: log ecutwfc echo is not {spec['ecutwfc']:.4f} Ry — log/input mismatch")
    check(re.search(rf"charge density cutoff\s*=\s*{spec['ecutrho']:.4f}\s+Ry", content),
          f"case{n}: log ecutrho echo is not {spec['ecutrho']:.4f} Ry — log/input mismatch")
    es = re.findall(r"!\s+total energy\s*=\s*([-\d.]+)\s+Ry", content)
    check(es, f"case{n}: no '! total energy' line in the log")
    log_energy[n] = float(es[-1])

# ── Layer 4/5: results.json consistency + reference tolerance ────────────────
res_path = os.path.join(WORKSPACE, "results.json")
check(os.path.isfile(res_path), "Missing: results.json")
with open(res_path) as f:
    results = json.load(f)
check(isinstance(results, dict) and "values" in results and "units" in results,
      "results.json must follow the {'values': {...}, 'units': {...}} schema")
values, units = results["values"], results["units"]

for n in (1, 2, 3):
    key = f"case{n}_energy_Ry"
    check(key in values, f"results.json values missing key: {key}")
    check(key in units, f"results.json units missing key: {key}")
    rep = float(values[key])
    check(abs(rep - log_energy[n]) <= refs["consistency_energy_tol_Ry"],
          f"{key}={rep:.8f} != log energy {log_energy[n]:.8f} Ry")
    ref, tol = refs["energy_Ry_ref"][f"case{n}"], refs["energy_Ry_tol"]
    check(abs(rep - ref) <= tol,
          f"{key}={rep:.8f} Ry differs from ref {ref:.8f} Ry by >{tol:.2e} — "
          f"the fixed run does not reproduce the calibrated result")

print("PASS: qe-error-diagnose")

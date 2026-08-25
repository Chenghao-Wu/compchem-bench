#!/usr/bin/env python3
"""
Structural lint checks for a CompChemBench task directory.

Usage: python3 lint_task.py <task_dir>
Exit 0 = pass, non-zero = fail.

Checks:
  1. Required files present
  2. task.toml schema (required keys, valid difficulty/capability)
  3. Tag vocabulary: tags[0] = software, exactly one method tag, no legacy
     category tags (category is retired; capability fields replace it)
  4. Dockerfile: no COPY of tests/ or solution/, no ADD, no COPY --from
  5. instruction.md: no reference-value leaks; documents the results.json
     values/units schema when the task produces results.json
  6. refs.json calibration gate: calibration_date is an ISO date,
     image_digest is a real sha256, and NO placeholder strings
     (NEEDS_CALIBRATION / PENDING_BACKFILL) anywhere in the file
  7. registry.toml ↔ task.toml consistency (name, difficulty, capability,
     capabilities_secondary, tags)
  8. Asset-integrity convention: if tests/verify.py reads from the workspace
     assets directory, tests/refs.json MUST pin every such asset by sha256
     under "asset_hashes" (verifiers never trust /workspace/assets copies)
"""

import sys
import os
import tomllib
import json
import re

REQUIRED_FILES = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "solution/solve.sh",
    "tests/test.sh",
    "tests/verify.py",
    "tests/refs.json",
]

REQUIRED_TASK_TOML_KEYS = {
    ("metadata", "name"),
    ("metadata", "difficulty"),
    ("metadata", "capability"),
    ("metadata", "tags"),
    ("environment", "build"),
    ("agent", "timeout_sec"),
    ("verifier", "timeout_sec"),
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# Capability = the cognitive skill the task measures (the primary
# organization axis; software is a secondary tag). Each task carries exactly
# one primary capability plus optional secondary aspects.
VALID_CAPABILITIES = {
    "system-construction",
    "adaptive-convergence",
    "property-estimation",
    "scientific-auditing",
    "failure-recovery",
    "cross-code-orchestration",
}

# Pre-capability taxonomy. These words must never appear as tags again —
# the capability field is the single source of truth for this axis.
LEGACY_CATEGORY_TAGS = {"input-prep", "execution", "analysis", "debugging", "workflow"}

# Tag vocabulary (see README §Conventions):
#   tags[0]     = software
#   exactly one = method
SOFTWARE_TAGS = {"ase", "lammps", "cp2k", "xtb", "qe", "rdkit"}
METHOD_TAGS = {"dft", "classical-md", "semi-empirical", "aimd", "cheminformatics"}

# Placeholder strings that mark un-calibrated reference data — any of these
# anywhere in refs.json (keys or values, nested) is a lint failure.
PLACEHOLDER_PATTERNS = ("NEEDS_CALIBRATION", "PENDING_BACKFILL")

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def error(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def check_required_files(task_dir):
    fails = 0
    for rel in REQUIRED_FILES:
        path = os.path.join(task_dir, rel)
        if not os.path.isfile(path):
            fails += error(f"Missing required file: {rel}")
    return fails


def check_tags(task_name, tags, source):
    fails = 0
    if not isinstance(tags, list) or not tags:
        return error(f"{source}: tags must be a non-empty list")
    prefix = task_name.split("-")[0]
    if tags[0] != prefix or tags[0] not in SOFTWARE_TAGS:
        fails += error(
            f"{source}: tags[0] must be the software tag {prefix!r} "
            f"(one of {sorted(SOFTWARE_TAGS)}), got {tags[0]!r}"
        )
    method = [t for t in tags if t in METHOD_TAGS]
    if len(method) != 1:
        fails += error(
            f"{source}: exactly one method tag from {sorted(METHOD_TAGS)} "
            f"required, found {method}"
        )
    legacy = [t for t in tags if t in LEGACY_CATEGORY_TAGS]
    if legacy:
        fails += error(
            f"{source}: legacy category tags {legacy} are retired — the "
            f"capability field replaces them"
        )
    return fails


def check_task_toml(task_dir):
    fails = 0
    path = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(path):
        return 1
    with open(path, "rb") as f:
        try:
            cfg = tomllib.load(f)
        except Exception as e:
            return error(f"task.toml parse error: {e}")

    for section, key in REQUIRED_TASK_TOML_KEYS:
        if section not in cfg or key not in cfg[section]:
            fails += error(f"task.toml missing [{section}].{key}")

    meta = cfg.get("metadata", {})
    if meta.get("difficulty") not in VALID_DIFFICULTIES:
        fails += error(f"task.toml metadata.difficulty must be one of {VALID_DIFFICULTIES}")
    if meta.get("capability") not in VALID_CAPABILITIES:
        fails += error(
            f"task.toml metadata.capability must be one of {sorted(VALID_CAPABILITIES)}"
        )
    secondary = meta.get("capabilities_secondary", [])
    if not isinstance(secondary, list):
        fails += error("task.toml metadata.capabilities_secondary must be a list")
    else:
        bad = [s for s in secondary if s not in VALID_CAPABILITIES]
        if bad:
            fails += error(
                f"task.toml capabilities_secondary must be one of "
                f"{sorted(VALID_CAPABILITIES)}, got {bad}"
            )
        if len(secondary) != len(set(secondary)):
            fails += error("task.toml capabilities_secondary contains duplicates")
        if meta.get("capability") in secondary:
            fails += error(
                "task.toml capabilities_secondary must not repeat the primary capability"
            )

    name = meta.get("name", os.path.basename(task_dir))
    tags = meta.get("tags", [])
    fails += check_tags(name, tags, "task.toml")

    return fails


def check_dockerfile(task_dir):
    fails = 0
    path = os.path.join(task_dir, "environment/Dockerfile")
    if not os.path.isfile(path):
        return 1
    content = open(path).read()
    # Must not COPY tests/ or solution/
    if re.search(r"COPY\s+\.?\/?tests[/\s]", content):
        fails += error("Dockerfile must not COPY tests/")
    if re.search(r"COPY\s+\.?\/?solution[/\s]", content):
        fails += error("Dockerfile must not COPY solution/")
    # ADD is forbidden outright (can fetch URLs / auto-extract — unpinned
    # content entering the image)
    if re.search(r"^\s*ADD\s+", content, re.MULTILINE):
        fails += error("Dockerfile must not use ADD (use COPY + pinned RUN commands)")
    # COPY --from can smuggle tests/solution in from another build stage or
    # an arbitrary external image
    if re.search(r"^\s*COPY\s+--from", content, re.MULTILINE | re.IGNORECASE):
        fails += error("Dockerfile must not use COPY --from (multi-stage copies are unverifiable)")
    return fails


def check_instruction(task_dir):
    fails = 0
    path = os.path.join(task_dir, "instruction.md")
    if not os.path.isfile(path):
        return 1
    content = open(path).read()
    # Heuristic: flag if instruction contains numeric reference values that look like
    # calibrated quantities (e.g. "= -76.3", "energy: -123.4 Ha")
    # This is intentionally conservative - maintainers should review flagged lines.
    suspicious = re.findall(r"[-+]?\d+\.\d{3,}\s*(Ha|eV|Å|kcal|kJ|K\b)", content)
    if suspicious:
        fails += error(
            f"instruction.md may contain reference values (review manually): {suspicious[:3]}"
        )
    # results.json schema convention: if the task produces results.json, the
    # instruction must document the values/units schema, and verify.py must
    # read results["values"] / results["units"].
    if "results.json" in content:
        if '"values"' not in content or '"units"' not in content:
            fails += error(
                "instruction.md must document the results.json "
                "{'values': {...}, 'units': {...}} schema"
            )
        vpath = os.path.join(task_dir, "tests/verify.py")
        if os.path.isfile(vpath):
            vcontent = open(vpath).read()
            if '["values"]' not in vcontent or '["units"]' not in vcontent:
                fails += error(
                    "tests/verify.py must read results.json via the values/units "
                    "schema (results[\"values\"] / results[\"units\"])"
                )
    return fails


def _walk_strings(obj):
    """Yield every string (keys and values, nested) in a JSON object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, str):
        yield obj


def check_refs_json(task_dir):
    fails = 0
    path = os.path.join(task_dir, "tests/refs.json")
    if not os.path.isfile(path):
        return 1
    with open(path) as f:
        try:
            refs = json.load(f)
        except Exception as e:
            return error(f"tests/refs.json parse error: {e}")

    # Calibration gate: placeholders anywhere (keys or values) are a failure.
    for s in _walk_strings(refs):
        for pat in PLACEHOLDER_PATTERNS:
            if pat in s:
                fails += error(f"tests/refs.json contains placeholder {pat!r}: {s!r}")

    for required_key in ("calibration_date", "image_digest"):
        if required_key not in refs:
            fails += error(f"tests/refs.json missing key: {required_key}")

    date = refs.get("calibration_date", "")
    if isinstance(date, str) and not ISO_DATE_RE.match(date):
        fails += error(f"tests/refs.json calibration_date must be ISO YYYY-MM-DD, got {date!r}")

    digest = refs.get("image_digest", "")
    if isinstance(digest, str) and not DIGEST_RE.match(digest):
        fails += error(
            f"tests/refs.json image_digest must be 'sha256:<64 hex>' "
            f"(from 'docker inspect'), got {digest!r}"
        )
    return fails


def check_asset_integrity(task_dir):
    """P2 convention: a verifier that reads /workspace/assets (agent-writable)
    must pin those assets by sha256 in refs.json 'asset_hashes'."""
    fails = 0
    vpath = os.path.join(task_dir, "tests/verify.py")
    if not os.path.isfile(vpath):
        return 0  # missing-file failure is reported elsewhere
    vcontent = open(vpath).read()
    reads_assets = re.search(
        r'/workspace/assets|WORKSPACE["\']?\s*,\s*["\']assets["\']|["\']assets/',
        vcontent,
    )
    if not reads_assets:
        return 0

    rpath = os.path.join(task_dir, "tests/refs.json")
    if not os.path.isfile(rpath):
        return 0
    with open(rpath) as f:
        try:
            refs = json.load(f)
        except Exception:
            return 0  # parse failure is reported elsewhere

    hashes = refs.get("asset_hashes")
    if not isinstance(hashes, dict) or not hashes:
        return error(
            "tests/verify.py reads /workspace/assets but tests/refs.json pins no "
            "'asset_hashes' — a verifier must never trust agent-writable asset "
            "copies (pin sha256 per asset; see README §Conventions)"
        )
    for rel, digest in hashes.items():
        if not isinstance(rel, str) or rel.startswith("/") or ".." in rel.split("/"):
            fails += error(f"refs.json asset_hashes key must be a safe relative path, got {rel!r}")
            continue
        if not (isinstance(digest, str) and DIGEST_RE.match(digest)):
            fails += error(
                f"refs.json asset_hashes[{rel!r}] must be 'sha256:<64 hex>', got {digest!r}"
            )
        if not os.path.isfile(os.path.join(task_dir, "environment", rel)):
            fails += error(
                f"refs.json asset_hashes pins {rel!r} but environment/{rel} does not exist"
            )
    return fails


def check_registry_consistency(task_dir):
    fails = 0
    registry_path = os.path.join(task_dir, "..", "..", "registry.toml")
    if not os.path.isfile(registry_path):
        return error(f"registry.toml not found at {os.path.normpath(registry_path)}")

    with open(registry_path, "rb") as f:
        try:
            registry = tomllib.load(f)
        except Exception as e:
            return error(f"registry.toml parse error: {e}")

    task_toml_path = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(task_toml_path):
        return 1
    with open(task_toml_path, "rb") as f:
        cfg = tomllib.load(f)
    meta = cfg.get("metadata", {})
    name = meta.get("name", os.path.basename(task_dir))

    entries = [t for t in registry.get("task", []) if t.get("name") == name]
    if not entries:
        return error(f"registry.toml has no [[task]] entry for {name!r}")
    entry = entries[0]

    for field in ("difficulty", "capability"):
        if entry.get(field) != meta.get(field):
            fails += error(
                f"registry.toml {field}={entry.get(field)!r} != "
                f"task.toml {field}={meta.get(field)!r}"
            )
    if set(entry.get("capabilities_secondary", [])) != set(meta.get("capabilities_secondary", [])):
        fails += error(
            f"registry.toml capabilities_secondary={entry.get('capabilities_secondary')!r} != "
            f"task.toml capabilities_secondary={meta.get('capabilities_secondary')!r}"
        )
    if set(entry.get("tags", [])) != set(meta.get("tags", [])):
        fails += error(
            f"registry.toml tags {sorted(entry.get('tags', []))} != "
            f"task.toml tags {sorted(meta.get('tags', []))}"
        )
    reg_path = entry.get("path", "")
    expected_rel = os.path.relpath(task_dir, os.path.join(task_dir, "..", ".."))
    if reg_path != expected_rel:
        fails += error(f"registry.toml path={reg_path!r} != actual {expected_rel!r}")

    return fails


def main():
    if len(sys.argv) != 2:
        print("Usage: lint_task.py <task_dir>")
        sys.exit(2)
    task_dir = sys.argv[1]
    if not os.path.isdir(task_dir):
        print(f"Not a directory: {task_dir}")
        sys.exit(2)

    total_fails = 0
    total_fails += check_required_files(task_dir)
    total_fails += check_task_toml(task_dir)
    total_fails += check_dockerfile(task_dir)
    total_fails += check_instruction(task_dir)
    total_fails += check_refs_json(task_dir)
    total_fails += check_asset_integrity(task_dir)
    total_fails += check_registry_consistency(task_dir)

    if total_fails == 0:
        print(f"OK: {task_dir}")
    else:
        print(f"FAILED: {total_fails} issue(s) in {task_dir}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Calibration driver for a CompChemBench task.

Builds the task image, runs the oracle solution N times inside it, and
reports the observed spread of every numeric key in results.json together
with the image digest and the sha256 of every asset — the raw material for
tests/refs.json.

Usage: .ci/calibrate.py tasks/<task-name> [--runs 5] [--platform linux/amd64]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task_dir")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--platform", default="linux/amd64")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    task_dir = os.path.realpath(args.task_dir)
    task_name = os.path.basename(task_dir)
    image = f"compchem-bench/{task_name}:ci"

    if not args.skip_build:
        print(f"[build] {image}", file=sys.stderr, flush=True)
        p = sh(["docker", "build", "--platform", args.platform,
                "--file", os.path.join(task_dir, "environment/Dockerfile"),
                "--tag", image, os.path.join(task_dir, "environment")])
        if p.returncode != 0:
            print(p.stdout[-4000:], p.stderr[-4000:], file=sys.stderr)
            sys.exit(f"build failed for {task_name}")

    p = sh(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    if p.returncode != 0:
        sys.exit(f"could not inspect {image}: {p.stderr}")
    image_digest = p.stdout.strip()

    # sha256 of every shipped asset, keyed relative to environment/
    asset_hashes = {}
    assets_root = os.path.join(task_dir, "environment", "assets")
    for root, _, files in os.walk(assets_root):
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, os.path.join(task_dir, "environment"))
            asset_hashes[rel] = sha256_file(full)

    runs = []
    for i in range(args.runs):
        print(f"[oracle {i + 1}/{args.runs}]", file=sys.stderr, flush=True)
        cid = sh(["docker", "create", "--platform", args.platform,
                  "--cpus=2", "--memory=4g", "--network=none",
                  "--entrypoint=/bin/bash", "--workdir=/workspace", image,
                  "-c", "mkdir -p /workspace /logs/verifier; "
                        "bash /solution/solve.sh; "
                        "echo $? > /logs/solve_exit_code.txt"]).stdout.strip()
        if not cid:
            sys.exit("docker create failed")
        sh(["docker", "cp", os.path.join(task_dir, "solution"), f"{cid}:/solution"])
        start = sh(["docker", "start", "-a", cid])

        with tempfile.TemporaryDirectory() as tmp:
            got = sh(["docker", "cp", f"{cid}:/workspace/results.json",
                      os.path.join(tmp, "results.json")])
            exitc = sh(["docker", "cp", f"{cid}:/logs/solve_exit_code.txt",
                        os.path.join(tmp, "exit.txt")])
            sh(["docker", "rm", "-f", cid])

            if exitc.returncode == 0:
                code = open(os.path.join(tmp, "exit.txt")).read().strip()
                if code != "0":
                    print(start.stdout[-3000:], start.stderr[-3000:],
                          file=sys.stderr)
                    sys.exit(f"solve.sh exited {code} on run {i + 1}")
            if got.returncode != 0:
                print(start.stdout[-3000:], start.stderr[-3000:],
                      file=sys.stderr)
                sys.exit(f"no results.json produced on run {i + 1}")
            with open(os.path.join(tmp, "results.json")) as f:
                runs.append(json.load(f)["values"])

    # Spread across runs, per key
    summary = {}
    for key in runs[0]:
        vals = [r[key] for r in runs]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool)
               for v in vals):
            lo, hi = min(vals), max(vals)
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            summary[key] = {"mean": mean, "min": lo, "max": hi,
                            "spread": hi - lo, "std": var ** 0.5,
                            "deterministic": hi == lo}
        else:
            summary[key] = {"values": vals,
                            "deterministic": len(set(map(str, vals))) == 1}

    report = {
        "task": task_name,
        "image": image,
        "image_digest": image_digest,
        "platform": args.platform,
        "runs": args.runs,
        "asset_hashes": asset_hashes,
        "observed": summary,
        "raw_runs": runs,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# Oracle solution for lammps-thermal-conductivity.
# Runs the provided Green-Kubo input at T*=1.0 and T*=0.4, then computes kappa
# from the HCACF files with the reference protocol.
set -euo pipefail
cd /workspace

cp /workspace/assets/therm.in ./therm.in
cp /workspace/assets/bead2.tersoff ./bead2.tersoff
cp /workspace/assets/data_T1.lammps ./data_T1.lammps
cp /workspace/assets/data_T04.lammps ./data_T04.lammps

export OMP_NUM_THREADS=1
lmp_serial -log log.T1  -var suffix T1  -in therm.in
lmp_serial -log log.T04 -var suffix T04 -in therm.in

python3 << 'PYEOF'
import json
import numpy as np

DT = 0.005
NEVERY = 5
DT_DATA = NEVERY * DT          # lag spacing in tau
KBT = 1.0
NC_REF = 5001                  # full-block Ncount at lag 0 = Nfreq/Nevery + 1
WINDOW = 10
NLAGS = 200


def parse_acf(path):
    """Return list of blocks; each block is a list of rows
    (index, TimeDelta, Ncount, c1, c2, c3)."""
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
                    row = [float(x) for x in parts[:6]]
                except ValueError:
                    continue
                cur.append(row)
    return blocks


def box_volume(path):
    """Read xlo xhi ylo yhi zlo zhi from a LAMMPS data file."""
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) == 4 and p[2] in ("xlo", "ylo", "zlo"):
                x0, x1 = float(p[0]), float(p[1])
                if p[2] == "xlo":
                    lx = x1 - x0
                elif p[2] == "ylo":
                    ly = x1 - x0
                else:
                    lz = x1 - x0
            if p[:1] == ["Atoms"]:
                break
    return lx * ly * lz


def kappa_from_acf(path, V, T):
    blocks = parse_acf(path)
    full = [b for b in blocks if len(b) >= NLAGS and b[0][2] >= NC_REF]
    if not full:
        raise RuntimeError(f"no complete blocks in {path}")

    G = np.zeros(NLAGS)
    for b in full:
        a = np.array(b)[:NLAGS]
        G += a[:, 3] + a[:, 4] + a[:, 5]
    G /= len(full)

    # cutoff from the averaged, smoothed normalized curve
    Gn = G / G[0]
    smooth = np.convolve(Gn, np.ones(WINDOW) / WINDOW, mode="valid")
    zeros = np.where(smooth < 0)[0]
    cutoff = int(round((zeros[0] + WINDOW) * 1.5)) if len(zeros) else NLAGS
    cutoff = min(cutoff, NLAGS)

    def kappa_curve(g):
        integ = np.cumsum(g[:cutoff]) * DT_DATA
        curve = integ / (3.0 * KBT * T * T * V)
        return curve[int(len(curve) * 0.8):]

    k = float(np.mean(kappa_curve(G)))

    # block-level standard error of the mean, same cutoff
    kb = []
    for b in full:
        a = np.array(b)[:NLAGS]
        gb = a[:, 3] + a[:, 4] + a[:, 5]
        kb.append(float(np.mean(kappa_curve(gb))))
    err = float(np.std(kb, ddof=1) / np.sqrt(len(kb))) if len(kb) > 1 else 0.0
    return k, err, len(full)


V_T1 = box_volume("data_T1.lammps")
V_T04 = box_volume("data_T04.lammps")

k1, e1, n1 = kappa_from_acf("J0Jt_T1.dat", V_T1, 1.0)
k04, e04, n04 = kappa_from_acf("J0Jt_T04.dat", V_T04, 0.4)

assert n1 == n04, f"block counts differ: T1={n1} T04={n04}"

results = {
    "values": {
        "kappa_T1": k1,
        "kappa_T04": k04,
        "kappa_err_T1": e1,
        "kappa_err_T04": e04,
        "n_blocks": n1,
    },
    "units": {
        "kappa_T1": "LJ reduced (1/(sigma*tau))",
        "kappa_T04": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T1": "LJ reduced (1/(sigma*tau))",
        "kappa_err_T04": "LJ reduced (1/(sigma*tau))",
        "n_blocks": "1",
    },
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"T=1.0 : kappa = {k1:.6f} ± {e1:.6f}  (n_blocks={n1}, V={V_T1:.4f})")
print(f"T=0.4 : kappa = {k04:.6f} ± {e04:.6f}  (n_blocks={n04}, V={V_T04:.4f})")
PYEOF

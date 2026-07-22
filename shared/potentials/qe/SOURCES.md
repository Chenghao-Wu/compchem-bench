# QE pseudopotentials — sources

All files in this directory are from **PSlibrary 1.0.0** (PBE set), the open
pseudopotential library maintained by A. Dal Corso and distributed by the
Quantum ESPRESSO project. PSlibrary files are freely redistributable (see
https://pseudopotentials.quantum-espresso.org and the PSlibrary paper,
J. Chem. Theory Comput. 2023, 19, 20, 6992–7006).

Downloaded 2026-07-20 from the official QE pseudopotential server:

| File | Source URL | sha256 |
|---|---|---|
| `Si.pbe-n-rrkjus_psl.1.0.0.UPF` | https://pseudopotentials.quantum-espresso.org/upf_files/Si.pbe-n-rrkjus_psl.1.0.0.UPF | `669fb75395a9d26973b0ea1ce8223bbcb30d3396c5d48bf5e794d1243c52375a` |
| `C.pbe-n-kjpaw_psl.1.0.0.UPF` | https://pseudopotentials.quantum-espresso.org/upf_files/C.pbe-n-kjpaw_psl.1.0.0.UPF | `8a25fbf64c4fa257c68c01dc9a96e5b23c6a5ac0b09f45f271e1c946a65ed657` |
| `O.pbe-n-kjpaw_psl.1.0.0.UPF` | https://pseudopotentials.quantum-espresso.org/upf_files/O.pbe-n-kjpaw_psl.1.0.0.UPF | `6d4f573d1f5d8fab1d334ed76fefbac21fdbb2c406af7f85ab8c6aab0e84ccc0` |

Naming convention: `<El>.pbe-n-<method>_psl.1.0.0.UPF` — PBE functional, no
nonlinear core correction, `rrkjus` = RRKJ ultrasoft, `kjpaw` = Kresse–Joubert
PAW, `psl.1.0.0` = PSlibrary release 1.0.0.

Tasks copy the files they consume into `environment/assets/pseudo/` and pin
them via `tests/refs.json` `asset_hashes` (README §Conventions → Asset
integrity).

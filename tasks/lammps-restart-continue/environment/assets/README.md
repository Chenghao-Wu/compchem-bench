# Assets

`equil.restart` — LAMMPS binary restart, generated deterministically on
x86_64 with the task's base image
(`lammps/lammps:patch_7Jan2022_ubuntu20.04_openmpi_py3`) on 2026-07-20:
500-atom LJ fluid (fcc 0.8442, lj/cut 2.5), velocity seed 99999,
1000 NVT steps at T=1.2, then `write_restart`. Regenerate by running the
same input in the base image if the binary format ever needs rebuilding.

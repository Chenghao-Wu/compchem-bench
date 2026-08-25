# CompChemBench task image — <software> <topic>
#
# Lint-enforced (do NOT violate):
#   * never COPY tests/ or solution/ (also not via COPY --from)
#   * never ADD
#
# Pin the software to an exact version for reproducibility. Pinned inventory
# (see DATASET_CARD §5):
#   * ASE    3.23.0   (pip, python:3.11.9-slim, numpy 1.26.4)
#   * RDKit  2024.9.5 (pip, python:3.11.9-slim)
#   * LAMMPS patch_7Jan2022 (lammps/lammps:patch_7Jan2022_ubuntu20.04_openmpi_py3)
#   * CP2K   2024.1   (cp2k/cp2k:2024.1_mpich_generic_psmp)
#   * xtb    6.7.1    (official static tarball, sha256-verified)
#   * QE     7.4      (conda-forge qe=7.4=hac89879_0, via micromamba)
#
# Example (ASE / RDKit — pip):
FROM python:3.11.9-slim

RUN pip install --no-cache-dir "ase==3.23.0" "numpy==1.26.4"

# For a task that ships inputs, copy them into the agent's asset dir:
COPY assets/ /workspace/assets/

WORKDIR /workspace

# Entrypoint is set by the CI runner; default is bash
CMD ["/bin/bash"]

# ── Notes for other software ───────────────────────────────────────────────────
#
# CP2K (psmp builds see all host cores; pin OMP threads to the 2-CPU quota):
#   FROM cp2k/cp2k:2024.1_mpich_generic_psmp
#   ENV OMP_NUM_THREADS=2
#   # data files live at /opt/cp2k/data/ (BASIS_MOLOPT, GTH_POTENTIALS)
#
# QE (conda-forge openmpi; pin threads + isolate the MPI singleton so it does
# not look for ssh — see tasks/qe-scf-si/environment/Dockerfile for the full
# micromamba fetch + sha256-pinned toolchain):
#   ENV PATH="/opt/conda/bin:${PATH}" \
#       OMP_NUM_THREADS=2 \
#       OMPI_ALLOW_RUN_AS_ROOT=1 \
#       OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
#       OMPI_MCA_plm=isolated
#
# xtb (official static tarball, sha256-verified — see tasks/xtb-*/Dockerfile):
#   curl + sha256 assert the tarball, extract to /usr/local/bin.

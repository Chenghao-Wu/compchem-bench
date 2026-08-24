FROM lammps/lammps:patch_7Jan2022_ubuntu20.04_openmpi_py3

USER root
RUN pip3 install --no-cache-dir "numpy==1.24.4" "matplotlib==3.7.5"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

FROM lammps/lammps:patch_7Jan2022_ubuntu20.04_openmpi_py3

# Python for post-processing
USER root
RUN apt-get update -q && apt-get install -y -q "python3=3.8.*" "python3-pip=20.0.*" --no-install-recommends \
    && pip3 install --no-cache-dir "numpy==1.24.4" \
    && rm -rf /var/lib/apt/lists/*

# Put the asset files where the agent can find them
COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

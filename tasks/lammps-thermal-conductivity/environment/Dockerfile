# lammps-thermal-conductivity: builds the modified LAMMPS (lammps_Ex0) from
# source. The many-body pair potentials (tersoff, sw, vashishta, ...) are
# modified so the sticker three-body interaction of the Liu & O'Connor
# associative-polymer model reproduces the intended physics; a stock LAMMPS
# image cannot run this system correctly. The committed tarball is the pinned,
# buildable source tree: serial build, C++17 (the -std=c++17 flag is enabled
# in src/MAKE/Makefile.serial), no external libraries.

FROM ubuntu:20.04

USER root
RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
    build-essential g++ make python3=3.8.* python3-pip=20.0.* \
    && rm -rf /var/lib/apt/lists/*

# Build lmp_serial from the pinned modified source.
COPY lammps_ex0.tar.gz /opt/
RUN tar xzf /opt/lammps_ex0.tar.gz -C /opt \
    && cd /opt/lammps-develop/src && make -j4 serial \
    && cp lmp_serial /usr/local/bin/lmp_serial \
    && rm -rf /opt/lammps-develop /opt/lammps_ex0.tar.gz

RUN pip3 install --no-cache-dir "numpy==1.24.4"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

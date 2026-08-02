FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    lammps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
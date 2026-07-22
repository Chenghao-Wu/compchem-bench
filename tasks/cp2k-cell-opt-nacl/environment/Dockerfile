FROM cp2k/cp2k:2024.1_mpich_generic_psmp

RUN apt-get update -q && apt-get install -y -q "python3=3.10.*" "python3-pip=22.0.*" --no-install-recommends \
    && pip3 install --no-cache-dir "numpy==1.26.4" "ase==3.23.0" \
    && rm -rf /var/lib/apt/lists/*


# Pin OMP threads to the container's 2-CPU quota: the psmp build otherwise
# spawns one thread per *host* core (cgroup quota is invisible to OpenMP),
# thrashing the quota to ~1 effective core (the same lesson QE's images already had).
ENV OMP_NUM_THREADS=2

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

FROM python:3.11.9-slim

# Pin ASE; the pinned LAMMPS wheel ships liblammps + Python bindings and is
# used by the verifier for the L4-lite "LAMMPS really reads the data file"
# check (read_data + run 0).
RUN pip install --no-cache-dir "ase==3.23.0" "numpy==1.26.4" "lammps==2023.8.2.3.1"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

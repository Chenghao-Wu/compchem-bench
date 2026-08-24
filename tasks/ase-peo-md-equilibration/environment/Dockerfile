FROM python:3.11.9-slim

# Pin ASE + RDKit versions for reproducibility (ETKDG embedding and seeded
# Langevin dynamics are deterministic per version+seed)
RUN pip install --no-cache-dir "ase==3.23.0" "rdkit==2024.9.5" "numpy==1.26.4"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

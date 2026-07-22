FROM python:3.11.9-slim

# Pin RDKit version for reproducibility (ETKDG embedding is deterministic
# per version+seed)
RUN pip install --no-cache-dir "rdkit==2024.9.5" "numpy==1.26.4"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

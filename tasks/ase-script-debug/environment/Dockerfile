FROM python:3.11.9-slim

# Pin ASE version for reproducibility (same base as the other ASE tasks)
RUN pip install --no-cache-dir "ase==3.23.0" "numpy==1.26.4"

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

FROM python:3.11.9-slim

# Pin ASE version for reproducibility
RUN pip install --no-cache-dir "ase==3.23.0" "numpy==1.26.4"

# Working directory for the agent
WORKDIR /workspace

# Entrypoint is set by the CI runner; default is bash
CMD ["/bin/bash"]

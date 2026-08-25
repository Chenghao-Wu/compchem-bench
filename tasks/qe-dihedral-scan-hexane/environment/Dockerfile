FROM python:3.11.9-slim

# ── QE 7.4 toolchain: micromamba + conda-forge (identical pinned toolchain to
# the other qe-* tasks in this benchmark; GitHub + conda-forge verified
# reachable from this runtime) ────────────────────────────────────────────────
# micromamba 2.8.1 static binary (GitHub release, sha256 pinned)
ARG MICROMAMBA_SHA256=a934c3709c997feae403a27fd1e321c106d26ffa4f294800ffb11cbc9a3e8515
RUN python3 -c "\
import io, hashlib, tarfile, urllib.request, os; \
url = 'https://github.com/mamba-org/micromamba-releases/releases/download/2.8.1-0/micromamba-linux-64.tar.bz2'; \
data = urllib.request.urlopen(url, timeout=600).read(); \
digest = hashlib.sha256(data).hexdigest(); \
assert digest == '$MICROMAMBA_SHA256', f'micromamba sha256 mismatch: {digest}'; \
tf = tarfile.open(fileobj=io.BytesIO(data), mode='r:bz2'); \
m = tf.extractfile('bin/micromamba'); \
open('/usr/local/bin/micromamba', 'wb').write(m.read()); \
os.chmod('/usr/local/bin/micromamba', 0o755)"

# QE 7.4 from conda-forge (exact build pinned: qe-7.4-hac89879_0, openmpi).
RUN micromamba create -y -p /opt/conda -c conda-forge "qe=7.4=hac89879_0" \
    && micromamba clean -afy

# pw.x runs as a 1-rank MPI singleton (no mpirun needed; OMPI_MCA_plm=isolated
# keeps the conda-forge openmpi build from looking for ssh). OMP threads are
# pinned to the container's 2-CPU quota (never let the binary
# see and oversubscribe the host cores).
ENV PATH="/opt/conda/bin:${PATH}" \
    OMP_NUM_THREADS=2 \
    OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    OMPI_MCA_plm=isolated

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

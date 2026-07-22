FROM python:3.11.9-slim

# xtb 6.7.1 (official grimme-lab binary release, linux-x86_64, fully static).
# Pinned by sha256; GFN2 parameters are built into the binary.
ARG XTB_SHA256=62a8d18778286e815292ee53d76ce447daf460a4dea3782c0f25cbac7019b5df
RUN python3 -c "\
import io, os, hashlib, tarfile, urllib.request; \
url = 'https://github.com/grimme-lab/xtb/releases/download/v6.7.1/xtb-6.7.1-linux-x86_64.tar.xz'; \
data = urllib.request.urlopen(url, timeout=300).read(); \
digest = hashlib.sha256(data).hexdigest(); \
assert digest == '$XTB_SHA256', f'xtb tarball sha256 mismatch: {digest}'; \
tarfile.open(fileobj=io.BytesIO(data), mode='r:xz').extractall('/opt', filter='data'); \
os.rename('/opt/xtb-dist', '/opt/xtb')"

ENV PATH="/opt/xtb/bin:${PATH}" \
    OMP_NUM_THREADS=1

COPY assets/ /workspace/assets/

WORKDIR /workspace

CMD ["/bin/bash"]

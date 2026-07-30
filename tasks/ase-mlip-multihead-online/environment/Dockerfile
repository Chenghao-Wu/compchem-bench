FROM public.ecr.aws/docker/library/python:3.11.9-slim@sha256:2856e6af199e8128161abd320575eb9b341f3b76f017b5d0c9cd364f60d8a050

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_VISIBLE_DEVICES="" \
    NVIDIA_VISIBLE_DEVICES=void \
    DP_BACKEND=pytorch \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    NUMEXPR_NUM_THREADS=4

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# The online task starts with only the CPU PyTorch stack. The agent must
# install every chemistry package and obtain both checkpoints at runtime.
RUN python -m pip install \
    "numpy==1.26.4" \
    "pillow==12.3.0"
RUN python -m pip install \
    "torch==2.10.0" \
    --index-url https://download.pytorch.org/whl/cpu
RUN python -m pip install --no-deps \
    "torchvision==0.25.0" \
    "torchaudio==2.10.0" \
    --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip check

COPY assets/ /workspace/assets/

RUN python -c "import importlib.util, pathlib, torch; assert torch.version.cuda is None; assert not torch.cuda.is_available(); assert importlib.util.find_spec('ase') is None; assert importlib.util.find_spec('deepmd') is None; assert importlib.util.find_spec('mattersim') is None; assert not pathlib.Path('/opt/models').exists(); assert not pathlib.Path('/workspace/models').exists(); print('CPU-only PyTorch bootstrap image check passed')"

WORKDIR /workspace
CMD ["/bin/bash"]

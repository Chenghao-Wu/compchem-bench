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

# Install a CPU-only PyTorch wheel before packages that depend on torch.
# Separate layers keep the large torch wheel cached if a later package changes.
RUN python -m pip install "numpy==1.26.4"
RUN python -m pip install "torch==2.10.0" \
    --index-url https://download.pytorch.org/whl/cpu
RUN python -m pip install --no-deps \
    "torchvision==0.25.0" \
    "torchaudio==2.10.0" \
    --index-url https://download.pytorch.org/whl/cpu
RUN python -m pip install \
        "ase==3.26.0" \
        "deepmd-kit==3.1.3" \
        "mattersim==1.2.2" \
    && python -m pip check
# MatterSim's resolved materials stack requires NumPy 2, while the DeepMD
# wheel loads libmpi lazily. Pin both final runtime artifacts explicitly.
RUN python -m pip install --no-deps \
        "numpy==2.4.6" \
        "mpich==5.0.1" \
    && python -m pip check

# Download official, versioned checkpoints and verify their known hashes.
RUN mkdir -p /opt/models \
    && curl -fL --retry 5 \
        "https://modelscope.cn/models/DeepModelingCommunity/DPA-3.2-5M/resolve/master/DPA-3.2-5M.pt" \
        -o /opt/models/DPA-3.2-5M.pt \
    && echo "876354744aeaae17b2639a6a690514470273784f2b4836280850f50cbb799165  /opt/models/DPA-3.2-5M.pt" \
        | sha256sum -c - \
    && curl -fL --retry 5 \
        "https://raw.githubusercontent.com/microsoft/mattersim/v1.2.2/pretrained_models/mattersim-v1.0.0-5M.pth" \
        -o /opt/models/mattersim-v1.0.0-5M.pth \
    && echo "e3df9fa708725e3d453140646c7d1838324b347a3d1214cf1440522146f872b5  /opt/models/mattersim-v1.0.0-5M.pth" \
        | sha256sum -c -

COPY assets/ /workspace/assets/

RUN python -c "import torch; from deepmd.calculator import DP; from mattersim.forcefield import MatterSimCalculator; assert torch.version.cuda is None; assert not torch.cuda.is_available(); DP(model='/opt/models/DPA-3.2-5M.pt', head='OMol25'); MatterSimCalculator(load_path='/opt/models/mattersim-v1.0.0-5M.pth', device='cpu'); print('CPU-only model-load smoke check passed')"

WORKDIR /workspace
CMD ["/bin/bash"]

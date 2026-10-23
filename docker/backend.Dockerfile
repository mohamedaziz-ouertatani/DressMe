# The backend's environment: Python 3.13 + PyTorch + the exact package versions of
# docker/constraints.txt. The code, data and models are NOT copied in:
# docker-compose.yml mounts the repository at /app.
#
# PyTorch is the CPU build by default (~0.2 GB instead of ~3-4 GB): the app only runs
# the trained models on one photo at a time, which the CPU does in well under a second
# (training needs the GPU, but that is not done here). docker-compose.gpu.yml builds the
# GPU (CUDA 12.6) variant instead, with TORCH_INDEX=.../cu126.
# exact Python + Debian release, so every rebuild starts from the same system
FROM python:3.13.17-slim-trixie

# OpenCV (used by rembg for background removal) needs these system libraries
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1

ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
# PyTorch is pinned here, not in constraints.txt: its CPU and GPU builds carry
# different labels (2.14.1+cpu / 2.14.1+cu126)
ARG TORCH_VERSION=2.14.1
ARG TORCHVISION_VERSION=0.29.1

WORKDIR /tmp/requirements
COPY requirements.txt requirements-models.txt docker/constraints.txt ./
COPY backend/requirements.txt backend-requirements.txt
# PyTorch first, from its own index (as in the README); the cache mount keeps the
# download between rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} --index-url ${TORCH_INDEX}
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -r requirements-models.txt -r backend-requirements.txt -c constraints.txt

WORKDIR /app/backend
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

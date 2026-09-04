# CUDA evaluation worker.
#
# Separate from the CPU image on purpose: the CUDA wheels are large, and the CPU
# demo stack must stay small and runnable without a GPU. This image only runs the
# worker — the API stays on CPU and hands heavy evaluations to this process.
#
# `AISHIELD_COMPUTE_DEVICE=cuda` makes the registry refuse to start rather than
# silently fall back to CPU, so a run recorded as CUDA really used CUDA.
# Ubuntu 24.04, because 22.04 ships only Python 3.10 and this project requires
# 3.11+. CUDA 12.6 is the first release with both a 24.04 base and published
# torch 2.13.0 wheels, so the base and the wheel index stay on one version.
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04@sha256:8aef630a54bc5c5146ae5ce68e6af5caa3df0fb690bb91544175c91f307e4356 AS runtime

# Set at build time to the digest of the image being produced; every recorded run
# copies it into the evidence envelope.
ARG AISHIELD_CONTAINER_IMAGE_DIGEST=""
ARG AISHIELD_GIT_COMMIT=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    AISHIELD_COMPUTE_DEVICE=cuda \
    AISHIELD_CONTAINER_IMAGE_DIGEST=${AISHIELD_CONTAINER_IMAGE_DIGEST} \
    AISHIELD_GIT_COMMIT=${AISHIELD_GIT_COMMIT}

RUN apt-get update \
    && apt-get install --no-install-recommends --yes python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 aishield \
    && useradd --system --uid 10001 --gid aishield --create-home aishield

ENV VIRTUAL_ENV=/opt/aishield PATH=/opt/aishield/bin:$PATH
RUN python3.12 -m venv "$VIRTUAL_ENV"

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# The CUDA wheels are pinned to the same torch version as the CPU image, so a
# result differs by device only, never by framework version.
RUN python -m pip install --no-cache-dir \
      torch==2.13.0 torchvision==0.28.0 \
      --index-url https://download.pytorch.org/whl/cu126 \
    && python -m pip install --no-cache-dir ".[ml,postgres,redis]"

# Only /app is chowned. A recursive chown over the virtualenv would copy every
# one of its ~6.7GB of files into a new layer, doubling the image; the worker
# only ever reads site-packages.
RUN mkdir -p /app/artifacts/models /app/data && chown -R aishield:aishield /app
USER aishield

CMD ["aishield-worker"]

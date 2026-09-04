FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217 AS runtime

# Set at build time to the digest of the image being produced, e.g.
#   docker build --build-arg AISHIELD_CONTAINER_IMAGE_DIGEST="$(...)" .
# Every recorded run copies it into the evidence envelope, so a result can be
# traced back to the exact image that produced it.
ARG AISHIELD_CONTAINER_IMAGE_DIGEST=""
ARG AISHIELD_GIT_COMMIT=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AISHIELD_CONTAINER_IMAGE_DIGEST=${AISHIELD_CONTAINER_IMAGE_DIGEST} \
    AISHIELD_GIT_COMMIT=${AISHIELD_GIT_COMMIT}

RUN groupadd --system --gid 10001 aishield \
    && useradd --system --uid 10001 --gid aishield --create-home aishield

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir \
      torch==2.13.0 torchvision==0.28.0 \
      --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir ".[ml,postgres,redis]"

RUN mkdir -p /app/artifacts/models /app/data && chown -R aishield:aishield /app
USER aishield

EXPOSE 8000
CMD ["uvicorn", "aishield.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

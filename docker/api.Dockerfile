FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

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

# ============================================================
# JurnalMap — Backend Dockerfile (Python / FastAPI)
#
# CPU-only PyTorch is installed to keep the image size manageable
# (~1.5 GB) while still enabling sentence-transformers embeddings for
# the research network graph.
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/models \
    TORCH_HOME=/app/models

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        mupdf \
        mupdf-tools \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Deps stage: install Python packages.
# CPU-only torch first to avoid pulling >2GB of CUDA wheels.
# ------------------------------------------------------------
FROM base AS deps

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.0 \
 && pip install -r requirements.txt

# ------------------------------------------------------------
# Runtime stage
# ------------------------------------------------------------
FROM base AS runtime

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin /usr/local/bin

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
 && mkdir -p /app/uploads /app/models \
 && chown -R appuser:appuser /app

WORKDIR /app

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/')" || exit 1

# NOTE: workers=1 because the queue worker holds shared state inside the
# process. Scale horizontally instead if you need higher throughput.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

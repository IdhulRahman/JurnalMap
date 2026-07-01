# ============================================================
# JurnalMap — Backend Dockerfile (Python / FastAPI)
# ============================================================
# Stage 1: Base
# ============================================================
FROM python:3.11-slim AS base

# Keep Python output unbuffered for container logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS deps needed by PyMuPDF and other native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        mupdf \
        mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Stage 2: Dependencies
# ============================================================
FROM base AS deps

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 3: Runtime
# ============================================================
FROM base AS runtime

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create upload directory with correct ownership
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

USER appuser

# Expose port (uvicorn default)
EXPOSE 8001

# Health check — calls the /api/ health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/')" || exit 1

# Entry point — production-grade with multiple workers
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]

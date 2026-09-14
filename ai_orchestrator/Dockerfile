# AI Orchestrator Dockerfile
#
# IMPORTANT: this image MUST be built with the REPOSITORY ROOT as the build
# context, because the application imports itself as the `ai_orchestrator`
# package (e.g. `from ai_orchestrator.core.openrouter_client import ...`).
# The package directory therefore has to exist at /app/ai_orchestrator.
#
# Build:
#   docker build -f ai_orchestrator/Dockerfile -t kraken-ai-orchestrator .
#
# GitHub Actions uses:
#   context: .
#   file: ai_orchestrator/Dockerfile

FROM python:3.11-slim

# System deps. curl is REQUIRED by the HEALTHCHECK below
# (python:3.11-slim does not ship curl).
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies first (better layer caching)
COPY ai_orchestrator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application source, laid out as a real importable package: /app/ai_orchestrator
COPY ai_orchestrator/ /app/ai_orchestrator/
COPY ai_orchestrator/pyproject.toml /app/pyproject.toml

# Editable install so `import ai_orchestrator` resolves to /app/ai_orchestrator
RUN pip install --no-cache-dir -e /app

# Runtime mount points (swarm configs are mounted into /app/config)
RUN mkdir -p /app/config /app/logs \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Run as a module so package-relative imports are unambiguous
CMD ["python", "-m", "ai_orchestrator.main"]
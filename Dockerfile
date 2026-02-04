# syntax=docker/dockerfile:1.6
FROM python:3.13-slim

# Basic runtime flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Where uv will create the project venv inside the container
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy only dependency manifests for layer caching
COPY pyproject.toml uv.lock ./

# Create venv + install deps (including dev deps for local dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv "$UV_PROJECT_ENVIRONMENT" \
 && uv sync --frozen

# Copy source (optional for dev; still useful so image can run without mounts)
COPY src ./src
COPY tests ./tests

# Create log dir
RUN mkdir -p /app/log

# Default command run CLI app
ENTRYPOINT ["uv", "run", "app"]

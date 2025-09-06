# syntax=docker/dockerfile:1

# ----------------------------
# Builder stage
# ----------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies needed for building Python wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Install Python dependencies into a temporary layer to leverage Docker cache
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /install/wheels -r requirements.txt

# ----------------------------
# Runtime stage
# ----------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="DevOps Team <devops@example.com>"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=base.settings \
    PORT=8000

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

WORKDIR /app

# Copy wheels from builder and install using --no-index to avoid hitting PyPI again
COPY --from=builder /install/wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*

# Copy project
COPY --chown=appuser:appuser . /app

# Ensure entrypoint is executable and prepare log directory
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/logs \
    && python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

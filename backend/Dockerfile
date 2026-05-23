# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: base — install Python dependencies with layer-cache optimisation
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app

# Python runtime flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system-level runtime dependencies
# curl is needed for the Docker healthcheck in production
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so pip install is cached independently of source
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: development — Flask dev server with auto-reload
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS development
COPY . .
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: production — gunicorn behind a non-root user
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS production

# Pin gunicorn to a known-good version
RUN pip install --no-cache-dir gunicorn==23.0.0

# Copy application source
COPY . .

# Create a non-root system user/group
RUN addgroup --gid 1001 --system appgroup \
    && adduser --uid 1001 --system --gid 1001 appuser

# Ensure the uploads directory exists and is writable by the app user
RUN mkdir -p /app/uploads && chown appuser:appgroup /app/uploads

USER appuser
EXPOSE 5000

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]

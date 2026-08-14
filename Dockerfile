# --- Build Stage ---
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies into virtual environment
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt


# --- Production Runner Stage ---
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime libraries & healthcheck tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment with installed packages from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . /app/

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create static, media, and log directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Set up non-root user for security and transfer ownership of /app and /opt/venv
RUN useradd -u 8888 appuser && chown -R appuser:appuser /app /opt/venv
USER appuser

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

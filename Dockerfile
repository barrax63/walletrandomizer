# Multi-stage Dockerfile for walletrandomizer
# Based on python:3.11-slim-bookworm

# Builder stage: Install dependencies in a virtual environment
FROM python:3.11-slim-bookworm AS builder

LABEL org.opencontainers.image.title="walletrandomizer" \
      org.opencontainers.image.description="Generates random BIP39 wallets, derives Bitcoin addresses under various derivation paths, and then queries their balances" \
      org.opencontainers.image.authors="Noah Nowak <nnowak@cryshell.com>" \
      org.opencontainers.image.url="https://github.com/barrax63/walletrandomizer" \
      org.opencontainers.image.source="https://github.com/barrax63/walletrandomizer" \
      org.opencontainers.image.documentation="https://github.com/barrax63/walletrandomizer/blob/main/README.md" \
      org.opencontainers.image.base.name="docker.io/library/python:3.11-slim-bookworm"

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages with C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    make \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv

# Activate venv and install Python dependencies
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage: Minimal image with just the application
FROM python:3.11-slim-bookworm AS runtime

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY walletrandomizer.py .
COPY web.py . 
COPY entrypoint.sh /entrypoint.sh
COPY templates/ ./templates/
COPY static/ ./static/

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

# Create data directory for output
RUN mkdir -p /data && chown -R appuser:appuser /data

# Set PATH to use venv
ENV PATH="/opt/venv/bin:$PATH"

# Switch to non-root user
USER appuser

# Expose port (for potential future web interface)
EXPOSE 5000

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD []
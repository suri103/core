FROM python:3.12-slim AS builder
WORKDIR /app

# Install build dependencies for C extensions (asyncpg, pydantic-core, hiredis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Optimize layer caching: Copy and install requirements separately
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final stage
FROM python:3.12-slim
WORKDIR /app

# Install runtime dependencies (e.g., curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Ensure alembic.ini is in the correct location
RUN cp /app/alembic.ini /app/alembic.ini 2>/dev/null || true

# Make startup script executable
RUN chmod +x /app/start.sh
RUN chmod +x /app/start.py

# Make migration script executable
RUN chmod +x /app/run_migrations.sh

# Make the process-type-aware healthcheck executable
RUN chmod +x /app/healthcheck.py

# Create non-root user for security (HIPAA Best Practice)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Keep the image and production compose topology on one port.
ENV PORT=3000
EXPOSE 3000

# Health check is process-type-aware (HIPAA: Monitoring uptime).
# Worker/beat containers have no HTTP listener, so probing /health there would
# crash-loop them; healthcheck.py switches probe by PROCESS_TYPE instead.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python /app/healthcheck.py || exit 1

# Start application (migrations run automatically via start.py)
CMD ["python", "/app/start.py"]

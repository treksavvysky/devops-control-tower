FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 1) Copy metadata + code
COPY pyproject.toml README.md ./
COPY devops_control_tower ./devops_control_tower
# (optional, if they exist)
# COPY scripts ./scripts
# COPY alembic ./alembic
# (optional but sensible)
COPY migrations ./migrations
COPY alembic.ini ./
# 2) Install the package
RUN pip install --no-cache-dir -e .
# or, if you don’t need editable inside Docker:
# RUN pip install --no-cache-dir .

# Create non-root user
RUN useradd --create-home --shell /bin/bash devops && \
    chown -R devops:devops /app
USER devops

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "devops_control_tower.main"]

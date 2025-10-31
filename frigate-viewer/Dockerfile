FROM python:3.11-slim-bullseye

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (if any are needed, e.g., for pip or SSL)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose default HTTP port
EXPOSE 8080

# Set environment variables for sensible defaults (can be overridden at runtime)
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8080

# Create a non-root user and switch to it
RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

# Entrypoint: use the provided run.sh for environment setup and execution
ENTRYPOINT ["sh", "run.sh"]

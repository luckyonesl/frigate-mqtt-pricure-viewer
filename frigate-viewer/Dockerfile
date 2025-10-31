# syntax=docker/dockerfile:1
# check=experimental=JSONArgsRecommended,StageNameCasing

FROM debian:trixie-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (if any are needed, e.g., for pip or SSL)
# # Prevent cache cleanup, because we use a mount cache
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
    --mount=type=cache,sharing=locked,target=/var/cache/apt --mount=type=cache,sharing=locked,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates tini curl jq python3-flask python3-paho-mqtt python3-requests

# Create a non-root user and switch to it
RUN useradd --no-create-home --shell /usr/sbin/nologin appuser && mkdir /home/appuser && chown appuser /home/appuser
USER appuser
WORKDIR /home/appuser

# use requirements and install Python dependencies
# try to use debian
# FROM python:3.11-slim-trixie
#RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt --mount=type=cache,sharing=locked,target=/home/appuser/.cache \
#    pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY app.py run.sh /home/appuser/

# Expose default HTTP port
EXPOSE 8080

# Set environment variables for sensible defaults (can be overridden at runtime)
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8080



# Entrypoint: use the provided run.sh for environment setup and execution
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh","run.sh"]

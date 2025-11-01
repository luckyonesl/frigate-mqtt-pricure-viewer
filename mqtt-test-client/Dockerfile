# syntax=docker/dockerfile:1
# check=experimental=JSONArgsRecommended,StageNameCasing
FROM debian:trixie-slim
# Install system dependencies (if any are needed, e.g., for pip or SSL)
# # Prevent cache cleanup, because we use a mount cache
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
    --mount=type=cache,sharing=locked,target=/var/cache/apt --mount=type=cache,sharing=locked,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates tini curl jq mosquitto-clients
COPY run_test.sh /
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh","run_test.sh"]

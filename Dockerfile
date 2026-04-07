# IEEE 2030.5 Gateway — Linux build environment
#
# Used for:
#   - Compiling the EPRI C client on macOS (C code requires Linux / epoll)
#   - Running the gateway in a container
#   - CI/CD
#
# Build:
#   docker build -t gateway .
#
# Run (development):
#   docker run --rm -it \
#     --network host \
#     -v $(pwd)/config:/app/config:ro \
#     gateway
#
# Run (with explicit config):
#   docker run --rm -it \
#     -v $(pwd)/config:/app/config:ro \
#     gateway --config /app/config/gateway.yaml

FROM ubuntu:24.04

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    libssl-dev \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source
COPY . .

# Build the EPRI C client
RUN cd epri_client && make

# Install Python package and dependencies
RUN pip3 install --break-system-packages -e ".[dev]"

# Certs and config are expected to be mounted at runtime
VOLUME ["/app/config"]

ENTRYPOINT ["python3", "-m", "gateway"]
CMD ["--config", "/app/config/gateway.yaml"]

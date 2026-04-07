# IEEE 2030.5 Gateway — Linux build environment
#
# Used for:
#   - Compiling the EPRI C client on macOS (C code requires Linux / epoll)
#   - Running the gateway in a container (production / CI)
#   - VS Code Dev Containers (.devcontainer/devcontainer.json)
#
# Production build & run:
#   docker build -t gateway .
#   docker run --rm -it \
#     --network host \
#     -v $(pwd)/config:/app/config:ro \
#     gateway --config /app/config/gateway.yaml

FROM ubuntu:24.04

# ── System dependencies (cached layer — rebuild only when this changes) ──────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    make \
    libssl-dev \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# ── Production build (skipped in Dev Containers — postCreateCommand handles it)
# Dev Containers mount the repo over /app after image build, so the COPY layer
# is replaced. The RUN steps below only run for production/CI builds.
COPY . .
RUN cd core && make
RUN uv sync --all-groups

# Certs and config mounted at runtime
VOLUME ["/app/config"]

ENTRYPOINT ["uv", "run", "python", "-m", "gateway"]
CMD ["--config", "/app/config/gateway.yaml"]

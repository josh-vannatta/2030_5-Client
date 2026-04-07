# Development Guide

## Prerequisites

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | ≥ 3.11 | |
| uv | any | `pip install uv` or `brew install uv` |
| GCC | ≥ 4.6 | Linux only — C client uses `epoll` |
| OpenSSL | ≥ 1.1.0 | `libssl-dev` on Ubuntu |
| Docker | any | Required on macOS |

The C binary (`core/build/client_test`) uses `epoll` and is **Linux-only**. On macOS, all development should happen inside Docker or the VS Code Dev Container.

---

## Recommended: VS Code Dev Container

The repo ships with `.devcontainer/devcontainer.json`. Open the project in VS Code and choose **Dev Containers: Reopen in Container**. On first open it:

1. Builds the Docker image (Ubuntu 24.04 + gcc + OpenSSL + Python + uv)
2. Compiles the C client (`make clean && make` in `core/`)
3. Installs Python dependencies (`uv sync --all-groups`)

Inside the container the full stack runs natively.

---

## Native Linux Setup

```bash
# System deps (Ubuntu / Debian)
sudo apt-get install gcc libc6-dev make libssl-dev python3 python3-pip curl

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Build the C client
cd core && make    # produces build/client_test
cd ..

# Install Python package + dev deps
uv sync --all-groups

# Generate dev certificates (first time only)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# Validate config
uv run python -m gateway --dry-run

# Run
uv run python -m gateway
```

---

## Running Tests

Tests are fully mocked — no hardware, no running server, no C binary required.

```bash
uv run pytest                       # all tests
uv run pytest -v                    # verbose output
uv run pytest -v -k bridge          # run a specific module
uv run pytest -v tests/test_config.py  # specific file
```

Tests live in `tests/`. The conftest in `tests/conftest.py` provides shared fixtures (mock Modbus adapter, sample config, etc.).

---

## Project Layout

```
gateway/
├── __main__.py       # Entry point: orchestrates startup and event loop
├── config.py         # YAML → typed dataclasses; env var overrides; startup validation
├── client.py         # Subprocess wrapper: spawns C binary, yields EVENT_JSON dicts
├── bridge.py         # DERControlBase → RegisterMap → Modbus writes; relinquish on end
├── device.py         # Reads telemetry registers at startup → DERState
├── settings.py       # DERState → DERCapability/Settings/Status/Availability XML
├── log.py            # Logging setup: text or JSON format, optional file output
└── protocols/
    ├── base.py       # FieldProtocol ABC (connect, read_register, write_register, close)
    ├── modbus.py     # pymodbus TCP adapter
    └── dnp3.py       # DNP3 stub — Phase 3
```

---

## Adding a Field Protocol

1. Add a new file in `gateway/protocols/` (e.g., `dnp3.py`)
2. Implement the `FieldProtocol` ABC from `protocols/base.py`:
   - `connect() -> None`
   - `read_register(address: int) -> int`
   - `write_register(address: int, value: int) -> None`
   - `close() -> None`
3. Add the new type to `config.py` (`protocol.type` field validation)
4. Instantiate it in `__main__.py` alongside the existing Modbus branch
5. Add tests in `tests/protocols/`

`bridge.py`, `device.py`, and `settings.py` depend only on `FieldProtocol` — they need no changes.

---

## Regenerating Certificates

The device certificate determines the SFDI. After any cert change, re-run:

```bash
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml
```

This generates a new ECDSA P-256 self-signed CA and device cert, computes the SFDI from the cert fingerprint, and writes it back to `gateway.yaml`. The server must also trust the new CA cert.

---

## Modifying the C Patch

`core/der_client.c` contains the `EVENT_JSON:` patch. The patched section emits one JSON line per DER event on stdout. If you change the JSON schema, update the corresponding parsing code in `gateway/client.py` and the tests in `tests/test_client.py`.

After any C change, rebuild:

```bash
cd core && make clean && make
```

---

## Docker Build

```bash
docker build -t gateway .
docker run --rm -it \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  gateway --config /app/config/gateway.yaml
```

The Dockerfile uses Ubuntu 24.04, builds the C binary, installs `uv`, and runs `uv sync`. The entrypoint is `uv run python -m gateway`.

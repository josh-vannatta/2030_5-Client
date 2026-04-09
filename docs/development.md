# Development

## Recommended workflow: VS Code Dev Container

The fastest and most reliable setup path is the included dev container. The repo ships with `.devcontainer/devcontainer.json`. Open the repository in VS Code and choose **Dev Containers: Reopen in Container**. On first open it will:

1. build the Docker image
2. compile the C client in `core/`
3. install Python dependencies with `uv` :contentReference[oaicite:2]{index=2}

Inside the container, the full stack runs in a Linux environment that matches the needs of the C client.

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | |
| uv | any | `pip install uv` or `brew install uv` |
| GCC | ≥ 4.6 | Linux only — C client uses `epoll` |
| OpenSSL | ≥ 1.1.0 | `libssl-dev` on Ubuntu |
| Docker | any | Required on macOS |

The C client is Linux-only because it depends on `epoll`. On macOS, use Docker or the VS Code Dev Container rather than trying to compile or run the C binary natively.

## Native Linux setup

For contributors working on Linux directly:

```bash id="q3tiz7"
# System deps (Ubuntu / Debian)
sudo apt-get install gcc libc6-dev make libssl-dev python3 python3-pip curl

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Build the C client
cd core && make
cd ..

# Install Python package + dev deps
uv sync --all-groups

# Generate dev certificates (first time only)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# Validate config
uv run python -m gateway --dry-run

# Run
uv run python -m gateway
````

This is the baseline local workflow for building and running the full stack. 

## Docker workflow

If you want a containerized runtime outside VS Code, build and run with Docker:

```bash id="5zml8h"
docker build -t gateway .
docker run --rm -it \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  gateway --config /app/config/gateway.yaml
```

The Dockerfile builds the C client, installs `uv`, installs Python dependencies, and runs the gateway through `python -m gateway`. 

## Day-to-day development loop

A typical iteration loop looks like this:

1. update Python or C code
2. rebuild the C client if `core/` changed
3. regenerate certs if device certificates changed
4. run `--dry-run` to validate config
5. run tests
6. run the gateway locally or in Docker/Dev Container

This keeps config, certificates, and the C binary aligned with the Python side.

## Running the gateway

The entry point is:

```bash id="mklv0p"
uv run python -m gateway
```

For config validation without starting the full runtime:

```bash id="d16aiv"
uv run python -m gateway --dry-run
```

The entry point orchestrates config load, logging, protocol setup, startup device reads, XML generation, C-client launch, and the event loop. 

## Running tests

Tests are fully mocked. No hardware, live server, or running C binary is required.

```bash id="32k1hv"
uv run pytest
uv run pytest -v
uv run pytest -v -k bridge
uv run pytest -v tests/test_config.py
```

Tests live under `tests/`, and shared fixtures are defined in `tests/conftest.py`. 

## Project layout

The main contributor-facing structure is:

```text id="1puic9"
gateway/
├── __main__.py       # Entry point: orchestrates startup and event loop
├── config.py         # YAML -> typed dataclasses; env overrides; validation
├── client.py         # Subprocess wrapper: spawns C binary, yields EVENT_JSON dicts
├── bridge.py         # DERControlBase -> RegisterMap -> Modbus writes; relinquish on end
├── device.py         # Reads telemetry registers at startup -> DERState
├── settings.py       # DERState -> DERCapability / DERSettings / DERStatus / DERAvailability XML
├── log.py            # Logging setup: text or JSON format
├── telemetry.py      # OpenTelemetry traces, metrics, and log bridge (optional)
└── protocols/
    ├── base.py       # FieldProtocol abstraction
    ├── modbus.py     # pymodbus TCP adapter
    └── dnp3.py       # DNP3 stub
```

This package structure is the main surface area for Python development. 

## Core development areas

### `config.py`

Owns YAML loading, typed config objects, environment overrides, and startup validation. Changes here usually affect config structure, validation rules, and startup UX. 

### `client.py`

Wraps the EPRI `client_test` subprocess. It is responsible for process lifecycle and for reading/parsing `EVENT_JSON:` from stdout. If the C-side event schema changes, this file must change too. 

### `bridge.py`

Contains the core control translation logic. This is where 2030.5 event payloads are mapped onto register writes and where `_active_registers` is tracked for relinquish behavior. 

### `device.py`

Reads startup telemetry from the field device and builds the `DERState` used for XML generation. 

### `settings.py`

Converts `DERState` into the four XML files consumed by the C client. 

### `protocols/`

Contains protocol adapters behind the `FieldProtocol` abstraction. Today this is primarily Modbus; DNP3 is a stub. 

## Adding a field protocol

The gateway is designed so that most of the code depends on a protocol abstraction rather than on Modbus directly.

To add a new protocol:

1. add a new file in `gateway/protocols/`
2. implement the `FieldProtocol` interface
3. add the new protocol type to config validation
4. instantiate it in startup/factory logic
5. add tests under `tests/protocols/` 

The required interface is conceptually:

* `connect()`
* `disconnect()` or `close()`
* `read_register(address) -> int`
* `write_register(address, value) -> None` 

Because `bridge.py`, `device.py`, and future telemetry code depend on the protocol abstraction, adding a new adapter should not require redesigning the rest of the gateway. 

## Certificates and SFDI generation

The device certificate determines the SFDI. After any cert change, regenerate certs and update config:

```bash id="x8er1o"
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml
```

This script:

* generates an ECDSA P-256 CA and device certificate
* computes the SFDI from the device certificate
* writes the computed SFDI back into `gateway.yaml`  

If you replace or regenerate the device cert without updating config, the SFDI used by the gateway will no longer match the certificate-derived identity expected by the C client and server flow.

## Modifying the C patch

`core/der_client.c` contains the patch that emits `EVENT_JSON:` lines. If you change that JSON schema, you must also update:

* the parsing logic in `gateway/client.py`
* any tests that assert on event payload structure 

After any C-side change, rebuild:

```bash id="m94r4k"
cd core && make clean && make
```

The Python side assumes the C client continues to emit one structured line per event transition.

## Typical change scenarios

### Change register mappings

* update `config/gateway.yaml`
* verify `RegisterMap` alignment in `config.py`
* update bridge tests if control mapping expectations changed

### Add a new control field

* update `bridge.py`
* map the field to a configured register key
* add or update unit tests
* confirm the event payload emitted by the C client contains the expected field

### Change startup telemetry fields

* update `ReadMap` / config handling
* update `device.py`
* update `DERState` / XML generation if needed
* add or update tests around defaults and partial reads

### Change event schema from C

* patch `core/der_client.c`
* rebuild C client
* update `gateway/client.py`
* update `tests/test_client.py`

## Observability

The gateway can export traces, metrics, and structured logs to any OTLP-compatible backend such as Grafana LGTM (Loki + Grafana + Tempo + Mimir) or a standalone OpenTelemetry Collector.

### Installing the packages

OTel support is an optional dependency group. Install it alongside core deps:

```bash
uv sync --group otel
```

The Dockerfile's existing `uv sync --all-groups` installs this group automatically. When the packages are absent and telemetry is enabled in config, the gateway logs a warning at startup and continues running normally — no crash, no degraded behavior.

### Enabling telemetry

**Option 1 — config file** (persistent, checked in with the repo):

```yaml
telemetry:
  enabled: true
  endpoint: http://otel-lgtm:4318
```

**Option 2 — environment variable** (useful for CI, containers, or ad-hoc runs):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4318
uv run python -m gateway
```

Setting `OTEL_EXPORTER_OTLP_ENDPOINT` activates telemetry automatically even when `enabled: false` in the YAML, which means you can leave the config file unchanged and control telemetry entirely through the environment.

### Local collector with Grafana LGTM

The easiest local stack is the all-in-one `grafana/otel-lgtm` Docker image, which exposes the OTLP HTTP port on `4318` and Grafana on `3000`:

```bash
docker run --rm -p 3000:3000 -p 4318:4318 grafana/otel-lgtm
```

Then run the gateway with the endpoint pointed at it:

```bash
OTEL_SERVICE_NAME=ieee2030-gateway \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
uv run python -m gateway --dry-run
```

Open `http://localhost:3000` (user `admin`, password `admin`) to see traces in Tempo, metrics in Mimir, and logs in Loki.

### Overriding individual signals

When routing signals to separate backends, use per-signal env vars:

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://tempo:4318/v1/traces
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://mimir:9090/otlp/v1/metrics
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://loki:3100/otlp/v1/logs
```

### What is exported

See [configuration.md — telemetry](configuration.md#telemetry) for the full signal reference. The short version:

* **Traces** — `gateway.run` root span with `epri_client.session` and per-event `bridge.event` child spans
* **Metrics** — counters for subprocess runs, DERControl events, Modbus operations, and errors; a histogram for subprocess session duration
* **Logs** — all Python `logging` output forwarded verbatim via a root-logger handler; the console/file settings in `logging:` are unaffected

### Disabling telemetry

Set `enabled: false` (the default) and ensure `OTEL_EXPORTER_OTLP_ENDPOINT` is not set. No OTel network connections are made and the `span()`, `count()`, and `record()` call sites in the gateway code resolve to no-ops at runtime.

## Logging and debug workflow

The gateway supports text and JSON logging. For local development, text is usually easiest to read. For structured debugging or ingestion into external tooling, JSON is more useful.  

Useful habits:

* run `--dry-run` before first execution after config changes
* use JSON logging when debugging event streams or startup failures
* inspect both Python logs and C subprocess output when troubleshooting runtime behavior

## Current implementation boundaries

Contributors should keep these Phase 0 boundaries in mind:

* startup telemetry is captured once, not continuously refreshed
* XML files are written once at startup
* DNP3 is not implemented yet
* there is no process supervision or restart loop yet
* live meter reads and live telemetry publishing are not yet implemented  

Those boundaries explain many current design choices and keep contributors from assuming functionality that does not exist yet.

## Documentation
* [readme.md](../README.md) — overview, quickstart, repo map
* [docs/architecture.md](architecture.md) — system boundaries, process model, IPC, data flows
* [docs/configuration.md](configuration.md) — app configuration, environment variables, 
* [docs/sequence.md](sequence.md) — lifecycle, runtime state, configuration, failure behavior
* [docs/development.md](development.md) — setup, testing, certificates, extension workflow
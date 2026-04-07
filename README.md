# IEEE 2030.5 DER Gateway

A two-process gateway that bridges an IEEE 2030.5 utility server to field devices over Modbus TCP today and DNP3 later. The Python gateway owns configuration, field-device reads/writes, XML generation, subprocess lifecycle, and runtime control translation, while the EPRI `client_test` C binary owns the 2030.5 wire protocol, TLS, EXI, resource traversal, and DERControl scheduling.

## Architecture

```text
[Utility / Aggregator Server]
        ↕ IEEE 2030.5 (HTTPS + EXI/XML)
┌──────────────────────────────────────┐
│ core/build/client_test               │  ← compiled C binary (EPRI)
│ owns 2030.5 stack                    │
│ emits EVENT_JSON: to stdout          │
└────────────────┬─────────────────────┘
                 │ JSON events (stdout pipe)
┌────────────────▼─────────────────────┐
│ gateway/ (Python)                    │
│ config · client · bridge             │
│ device · settings · log              │
│ protocols/modbus · protocols/dnp3    │
└────────────────┬─────────────────────┘
                 │ Modbus TCP / DNP3
┌────────────────▼─────────────────────┐
│ RTU / Inverter / Battery / DER       │
└──────────────────────────────────────┘
````

The system has two hard boundaries:

* **Northbound:** IEEE 2030.5 utility server
* **Southbound:** field device over Modbus TCP today, with DNP3 planned later 

### Responsibilities

**C client (`core/build/client_test`)**

* mutual-auth TLS
* EXI encoding/decoding
* 2030.5 resource discovery and traversal
* DERControl scheduling
* certificate-based device identity 

**Python gateway (`gateway/`)**

* config loading and validation
* startup device-state reads
* XML generation for 2030.5 settings
* subprocess management
* `EVENT_JSON:` parsing
* DERControl-to-register translation
* active register tracking and relinquish behavior 

## What it does

At startup, the gateway loads `gateway.yaml`, validates config and certificate paths, connects to the field device, reads a startup telemetry snapshot, writes four 2030.5 XML settings files, and then starts the C client. After that, it enters an event loop: the C client emits `EVENT_JSON:` lines on stdout, and the Python bridge translates those DERControl events into field-protocol register writes.  

In short:

* **Northbound:** field-device reads → `DERState` → XML files → C client → 2030.5 server 
* **Southbound:** server DERControl → C scheduling → `EVENT_JSON:` → Python bridge → Modbus register writes 

## Runtime lifecycle

The gateway runs through four phases:

1. **INIT** — load config, configure logging, build the bridge
2. **STARTUP** — connect protocol, read device state, write XML, spawn C client
3. **EVENT LOOP** — parse `EVENT_JSON:` and apply `start`, `end`, or `default_control`
4. **TEARDOWN** — stop subprocess and disconnect protocol adapter 

### Startup sequence

```text
load config
  → connect field protocol
  → read device registers
  → build DERState
  → write settings XML
  → spawn client_test
  → 2030.5 resource discovery
  → subscribe to DERControl
  → EVENT_JSON loop
  → write field registers on DER events
```

One important runtime detail: the XML settings files are written **once at startup**. They are not continuously refreshed in the current implementation. Another important caveat: if the gateway crashes mid-event, the device keeps the last written setpoints; registers are not automatically relinquished on crash.  

## Prerequisites

| Dependency | Version | Notes                                 |
| ---------- | ------- | ------------------------------------- |
| Python     | ≥ 3.11  |                                       |
| uv         | any     | `pip install uv` or `brew install uv` |
| GCC        | ≥ 4.6   | Linux only — C client uses `epoll`    |
| OpenSSL    | ≥ 1.1.0 | `libssl-dev` on Ubuntu                |
| make       | any     |                                       |
| Docker     | any     | Required on macOS                     |

The C client is Linux-only because it uses `epoll`; on macOS, use Docker or the VS Code Dev Container.  

## Quickstart

### Docker (macOS or Linux)

```bash
# 1. Clone
git clone <this-repo> && cd 2030_5-client

# 2. Generate dev certificates (computes SFDI, updates gateway.yaml)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# 3. Copy and edit config for your server and device
cp config/gateway.yaml config/my-gateway.yaml
# Edit: server.uri, server.interface, protocol.modbus.host, protocol.modbus.reads.*

# 4. Build and run
docker build -t gateway .
docker run --rm -it \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  gateway --config /app/config/my-gateway.yaml
```

### VS Code Dev Container

The repo ships with `.devcontainer/`. Open the project in VS Code and choose **Dev Containers: Reopen in Container**. On first open it will:

1. build the Docker image
2. compile the C client
3. install Python dependencies with `uv`  

### Native Linux

```bash
# 1. System dependencies (Ubuntu / Debian)
sudo apt-get install gcc libc6-dev make libssl-dev python3 python3-pip curl

# 2. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Build the C client
cd core && make
cd ..

# 4. Install Python deps
uv sync --all-groups

# 5. Generate dev certs (first time only)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# 6. Validate config
uv run python -m gateway --dry-run

# 7. Run
uv run python -m gateway
```

These are the supported setup paths today. 

## Configuration

All runtime configuration lives in `config/gateway.yaml` by default. Secrets and identity values can also be overridden with environment variables. 

| Env var        | Config key    |
| -------------- | ------------- |
| `GATEWAY_SFDI` | `device.sfdi` |
| `GATEWAY_PIN`  | `device.pin`  |
| `GATEWAY_CERT` | `device.cert` |

### Key fields

```yaml
device:
  sfdi: "320841683177"               # Derived from cert — run gen_dev_certs.py
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"                      # Optional in-band registration PIN

server:
  interface: "eth0"
  uri: "https://192.168.1.100/sep2"
  command: "all"                     # register | all | metering | fsa

protocol:
  type: modbus
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:                       # Control outputs written on DER events
      active_power: 40100
      reactive_power: 40101
      max_power_limit: 40102
      ramp_time: 40103
      connect: 40104
      energize: 40105
    reads:                           # Telemetry inputs read at startup
      inverter_status: 30201
      gen_connect_status: 30202
      state_of_charge: 30200
      available_w: 30203
      available_var: 30204
      rated_w: 30300
      rated_va: 30301
      rated_ah: 30302
      max_w: 30303
      max_a: 30304

logging:
  level: INFO
  format: text                       # text | json
```

The SFDI is derived from the device certificate rather than chosen arbitrarily. `scripts/gen_dev_certs.py` generates dev certs, computes the SFDI, and writes it back to `gateway.yaml`.  

## Project structure

```text
2030_5-client/
├── core/                  # EPRI C client (modified)
│   ├── Makefile           # Linux build
│   ├── der_client.c       # patched: emits EVENT_JSON lines
│   └── build/client_test  # compiled binary
│
├── gateway/               # Python package
│   ├── __main__.py        # entry point: python -m gateway
│   ├── config.py          # YAML loading, validation, RegisterMap, ReadMap
│   ├── client.py          # subprocess wrapper, EVENT_JSON parsing
│   ├── bridge.py          # DERControl events -> field protocol writes
│   ├── device.py          # reads live device state from field protocol
│   ├── settings.py        # generates 2030.5 settings XML from DERState
│   ├── log.py             # structured logging
│   └── protocols/
│       ├── __init__.py    # FieldProtocol abstraction
│       ├── modbus.py      # pymodbus TCP adapter
│       └── dnp3.py        # DNP3 stub
│
├── tests/
├── scripts/
├── config/
├── .devcontainer/
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

This structure matches the current separation of responsibilities in both the Python package and the modified C client.  

## Running tests

Tests are fully mocked. No hardware, no running 2030.5 server, and no live C binary are required.

```bash
uv run pytest
uv run pytest -v
uv run pytest -v -k bridge
```

The current test suite is organized under `tests/`. 

## Current status

### Implemented now

* config loading and validation
* Modbus adapter
* startup device reads
* XML generation
* subprocess lifecycle management
* `EVENT_JSON` parsing
* DERControl event translation
* active register tracking and relinquish on `end`
* mocked test coverage  

### Not implemented yet

* live telemetry updates after startup
* meter readings from actual device values
* process supervision and restart after C-client crash
* DNP3 implementation
* OpenFMB / MQTT / NATS integration
* richer notification / subscription / event-response flows 

### Proposed next phases

* periodic telemetry polling and live DERStatus / DERAvailability updates
* live meter reads and `MirrorMeterReading`
* resilience features like process restart and reconnect
* DNP3 adapter implementation  

## How the C patch works

`core/der_client.c` emits one `EVENT_JSON:` line per DER event transition. The Python side reads stdout line-by-line and yields parsed dicts for any line that starts with `EVENT_JSON:`. This is the only C→Python IPC channel in the current design.  

Example:

```text
EVENT_JSON:{"type":"start","mrid":"abc123","start":1700000000,"duration":900,"control":{"opModFixedW":8000,"rampTms":60}}
EVENT_JSON:{"type":"end","mrid":"abc123"}
EVENT_JSON:{"type":"default_control","control":{"opModMaxLimW":10000,"opModConnect":true}}
```

## Documentation

* `README.md` — overview, quickstart, repo map
* [docs/architecture.md](docs/architecture.md) — system boundaries, process model, IPC, data flows
* [docs/configuration.md](docs/configuration.md) — configuration files, environment variables, certs
* [docs/sequence.md](docs/sequence.md) — lifecycle, runtime state, configuration, failure behavior
* [docs/development.md](docs/development.md) — setup, testing, certificates, extension workflow

## References

* [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client)
* [IEEE 2030.5 Standard](https://standards.ieee.org/standard/2030_5-2018.html)
* [CSIP (Common Smart Inverter Profile)](https://sunspec.org/csip/)
* [pymodbus documentation](https://pymodbus.readthedocs.io/)
* [uv documentation](https://docs.astral.sh/uv/)

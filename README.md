# IEEE 2030.5 DER Gateway

A Python integration layer that bridges an IEEE 2030.5 utility server to field devices via Modbus TCP or DNP3. The Python layer manages configuration, device state, and field protocol communication. The [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client) handles the 2030.5 protocol (HTTP/TLS, EXI/XML, event scheduling, and server communication).

## Architecture

```
[Utility / Aggregator Server]
        ↕ IEEE 2030.5  (HTTPS + EXI/XML)
 ┌─────────────────────────────────┐
 │  core/build/client_test  │  ← compiled C binary (EPRI)
 │  emits EVENT_JSON: to stdout    │
 └──────────────┬──────────────────┘
                │ JSON events (stdout pipe)
 ┌──────────────▼──────────────────┐
 │  gateway/  (Python)             │
 │  config · client · bridge       │
 │  device · settings · log        │
 └──────────────┬──────────────────┘
                │ Modbus TCP / DNP3
 ┌──────────────▼──────────────────┐
 │  RTU / Inverter / Battery       │
 └─────────────────────────────────┘
```

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | |
| uv | any | `pip install uv` or `brew install uv` |
| GCC | ≥ 4.6 | Linux only — C code uses `epoll` |
| OpenSSL | ≥ 1.1.0 | `libssl-dev` on Ubuntu |
| make | any | |
| Docker | any | Required on macOS (no native Linux build) |

> **macOS**: The C client uses Linux-specific `epoll` and cannot compile or run natively. Use Docker or the VS Code Dev Container.

---

## Quickstart — Docker (macOS or Linux)

```bash
# 1. Clone
git clone <this-repo> && cd 2030_5-client

# 2. Generate dev certificates (computes SFDI, updates gateway.yaml)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# 3. Edit config for your server and device
cp config/gateway.yaml config/my-gateway.yaml
# Edit: server.uri, server.interface, protocol.modbus.host, reads.*

# 4. Build image and run
docker build -t gateway .
docker run --rm -it \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  gateway --config /app/config/my-gateway.yaml
```

---

## VS Code Dev Container

The repo ships with a `.devcontainer/` configuration. Open the project in VS Code and choose **Dev Containers: Reopen in Container**. On first open it will:

1. Build the Docker image (Ubuntu 24.04 + gcc + OpenSSL + Python + uv)
2. Compile the C client inside the container (`make clean && make`)
3. Install all Python dependencies (`uv sync --all-groups`)

Inside the container the full stack runs natively — the C binary is arm64 Linux, matching the container OS.

---

## Native Linux Build

```bash
# 1. System dependencies (Ubuntu / Debian)
sudo apt-get install gcc libc6-dev make libssl-dev python3 python3-pip curl

# 2. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Build the C client
cd core && make    # → build/client_test
cd ..

# 4. Install Python package
uv sync --all-groups      # creates .venv, installs all deps

# 5. Generate dev certs (first time only)
uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

# 6. Validate config
uv run python -m gateway --dry-run

# 7. Run
uv run python -m gateway
```

---

## Configuration

`config/gateway.yaml` is the single config file. Secrets can be injected via environment variables:

| Env var | Config key |
|---|---|
| `GATEWAY_SFDI` | `device.sfdi` |
| `GATEWAY_PIN` | `device.pin` |
| `GATEWAY_CERT` | `device.cert` |

### Key fields

```yaml
device:
  sfdi: "320841683177"               # Derived from cert — run gen_dev_certs.py
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"                      # In-band registration PIN (optional)

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
    registers:                       # Control outputs (written on DER events)
      active_power: 40100
      reactive_power: 40101
      max_power_limit: 40102
      ramp_time: 40103
      connect: 40104
      energize: 40105
    reads:                           # Telemetry inputs (read at startup)
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

---

## Project Structure

```
2030_5-client/
├── core/                  # EPRI C client (modified)
│   ├── Makefile                  # Linux build (replaces bash4-dependent build.sh)
│   ├── der_client.c              # patched: emits EVENT_JSON: lines on DER events
│   └── build/client_test         # compiled binary (after make)
│
├── gateway/                      # Python package
│   ├── __main__.py               # entry point: python -m gateway
│   ├── config.py                 # YAML loading, validation, RegisterMap, ReadMap
│   ├── client.py                 # subprocess wrapper — spawns binary, yields events
│   ├── bridge.py                 # DERControl events → field protocol writes
│   ├── device.py                 # reads live device state from field protocol
│   ├── settings.py               # generates settings/*.xml from DERState
│   ├── log.py                    # structured logging (text or JSON)
│   └── protocols/
│       ├── __init__.py           # FieldProtocol abstract base
│       ├── modbus.py             # pymodbus TCP adapter
│       └── dnp3.py               # DNP3 stub (Phase 4)
│
├── tests/
│   ├── conftest.py               # shared fixtures
│   ├── test_config.py
│   ├── test_bridge.py
│   ├── test_client.py
│   ├── test_device.py
│   ├── test_settings.py
│   └── protocols/
│       └── test_modbus.py
│
├── scripts/
│   └── gen_dev_certs.py          # generate ECDSA P-256 dev certs + compute SFDI
│
├── config/
│   ├── gateway.yaml              # example configuration
│   └── certs/                    # certificate storage (gitignored)
│       ├── device.pem            # device cert + private key
│       └── ca/ca.pem             # trusted CA certificate
│
├── .devcontainer/
│   └── devcontainer.json         # VS Code Dev Container config
├── Dockerfile                    # Linux build env + runtime
├── pyproject.toml                # Python package + uv dependency groups
└── uv.lock                       # pinned dependency lockfile
```

---

## Running Tests

```bash
uv run pytest          # all 62 tests, no hardware required
uv run pytest -v -k bridge   # run a specific module
```

---

## Development Phases

### Phase 0 — Foundation

Everything needed to go from zero to a structurally complete gateway.

| What | Files | Notes |
|---|---|---|
| **Linux build** | [core/Makefile](core/Makefile) | Replaces the bash 4-only `build.sh`; works with gcc/clang |
| **C patch** | [core/der_client.c](core/der_client.c) | Added `EVENT_JSON:` stdout lines for `start`, `end`, `default_control` events; Python reads these |
| **Config** | [gateway/config.py](gateway/config.py) | Typed dataclasses; YAML load + env var overrides; validates cert paths at startup |
| **Subprocess wrapper** | [gateway/client.py](gateway/client.py) | Spawns `client_test`, reads stdout line-by-line, yields parsed JSON dicts |
| **Bridge** | [gateway/bridge.py](gateway/bridge.py) | Maps `DERControlBase` fields to Modbus register writes; tracks active registers for relinquish |
| **DER settings XML** | [gateway/settings.py](gateway/settings.py) | Generates `DERCapability`, `DERSettings`, `DERStatus`, `DERAvailability` XML from a `DERState` dataclass |
| **Device state read** | [gateway/device.py](gateway/device.py) | Reads live telemetry from field device at startup; populates `DERState` for settings XML |
| **Modbus adapter** | [gateway/protocols/modbus.py](gateway/protocols/modbus.py) | pymodbus TCP wrapper behind the `FieldProtocol` abstract interface |
| **DNP3 stub** | [gateway/protocols/dnp3.py](gateway/protocols/dnp3.py) | Raises `NotImplementedError` — placeholder for Phase 4 |
| **Entry point** | [gateway/__main__.py](gateway/__main__.py) | Startup sequence: connect protocol → read device state → write XML → launch C binary → event loop |
| **Logging** | [gateway/log.py](gateway/log.py) | `text` or `json` format; optional file output |
| **Dev certs** | [scripts/gen_dev_certs.py](scripts/gen_dev_certs.py) | Generates ECDSA P-256 self-signed CA + device cert; computes SFDI from PEM bytes (matches C algorithm); auto-updates `gateway.yaml` |
| **Docker** | [Dockerfile](Dockerfile) | Ubuntu 24.04; gcc + OpenSSL + uv; works as both production image and Dev Container base |
| **Dev Container** | [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) | Compiles C binary and installs Python deps on first open; arm64-aware |
| **Tests** | [tests/](tests/) | 62 tests; all mocked — no hardware or running server required |

**Startup sequence (Phase 0 complete):**
```
load config → connect Modbus → read device registers → write settings XML
  → spawn client_test → EVENT_JSON loop → write Modbus registers on DER events
```

**What Phase 0 does NOT do:**
- Live telemetry updates after startup (DERStatus/Availability are static after launch)
- Meter readings from the device (C code uses hardcoded values)
- Process supervision / restart on C binary crash
- OpenFMB / DNP3 / Modbus Masters
  - MQTT support (DNP3 / Modbus config)
  - NATS support (for OpenFMB)
- Telemetry, Metering, Periodic Polling
- Notification, Subscription
- DERControl or Event -> Response

---

### Phase 1 — Live Telemetry *(proposal)*

- Periodic Modbus poll → PUT updated `DERStatus` / `DERAvailability` directly to server
- Live meter reads → POST `MirrorMeterReading` from actual device values
- Process restart loop with exponential backoff

### Phase 2 — Resilience *(proposal)*

- C process supervision and restart
- Modbus auto-reconnect
- Health check HTTP endpoint

### Phase 3 — DNP3 or OpenFMB *(proposal)*

- Implement `Dnp3Adapter` using `pydnp3` or equivalent

---

## How the C Patch Works

`core/der_client.c` emits one `EVENT_JSON:` line per DER event transition:

```
EVENT_JSON:{"type":"start","sfdi":320841683177,"mrid":"0102...","description":"Curtail 50%","control":{"opModFixedW":-50,"rampTms":100}}
EVENT_JSON:{"type":"end","sfdi":320841683177,"mrid":"0102...","description":"Curtail 50%"}
EVENT_JSON:{"type":"default_control","sfdi":320841683177,"description":"Default","control":{"opModFixedW":0}}
```

`gateway/client.py` reads stdout line-by-line and yields parsed dicts for lines starting with `EVENT_JSON:`. All other C output (connection status, schedule prints) goes to stderr as plain debug text.

---

## How SFDI is Computed

The SFDI is derived from the device certificate file — it is **not** arbitrary. The C binary computes it from the raw PEM bytes:

```python
sha256(pem_bytes)[:20]    # → LFDI (20 bytes)
lfdi[:5] >> 4             # → 36-bit value
value * 10 + check_digit  # → SFDI (decimal, with check digit)
```

`scripts/gen_dev_certs.py` runs this same algorithm in Python after generating the cert, and writes the result to `gateway.yaml`. If you regenerate certs you must re-run the script — the SFDI will change.

---

## References

- [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client)
- [IEEE 2030.5 Standard](https://standards.ieee.org/standard/2030_5-2018.html)
- [CSIP (Common Smart Inverter Profile)](https://sunspec.org/csip/)
- [pymodbus documentation](https://pymodbus.readthedocs.io/)
- [uv documentation](https://docs.astral.sh/uv/)

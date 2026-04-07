# IEEE 2030.5 DER Gateway

A Python integration layer that bridges an IEEE 2030.5 utility server to field devices via Modbus TCP or DNP3. The Python layer manages configuration, device state, and field protocol communication. The [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client) handles the 2030.5 protocol (HTTP/TLS, EXI/XML, event scheduling, and server communication).

## Architecture

```
[Utility / Aggregator Server]
        ↕ IEEE 2030.5  (HTTPS + EXI/XML)
 ┌─────────────────────────────────┐
 │  epri_client/build/client_test  │  ← compiled C binary (EPRI)
 │  emits EVENT_JSON: to stdout    │
 └──────────────┬──────────────────┘
                │ JSON events (stdout pipe)
 ┌──────────────▼──────────────────┐
 │  gateway/  (Python)             │
 │  config · client · bridge       │
 │  settings · log                 │
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
| GCC | ≥ 4.6 | Linux only (C code uses `epoll`) |
| OpenSSL | ≥ 1.1.0 | `libssl-dev` on Ubuntu |
| make | any | |
| Docker | any | macOS dev / CI |

> **macOS**: The C client uses Linux-specific `epoll`. Build and run via Docker (see below).

---

## Quickstart — Docker (macOS or Linux)

```bash
# 1. Clone
git clone <this-repo>
cd 2030_5-client

# 2. Copy and edit config
cp config/gateway.yaml config/my-gateway.yaml
# Edit: server.uri, device.sfdi, device.cert, protocol.modbus.host …

# 3. Place certs
cp /path/to/device.pem config/certs/device.pem
mkdir -p config/certs/ca && cp /path/to/ca*.pem config/certs/ca/

# 4. Build and run
docker build -t gateway .
docker run --rm -it \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  gateway --config /app/config/my-gateway.yaml
```

---

## Native Linux Build

### 1. Install dependencies

```bash
# Ubuntu / Debian
sudo apt-get install gcc make libssl-dev python3 python3-pip
```

### 2. Build the C client

```bash
cd epri_client
make              # optimized build  →  build/client_test
make debug        # debug build with symbols
make clean        # remove build/
```

If your OpenSSL is not in `/usr`:
```bash
make OPENSSL_PREFIX=/opt/openssl
```

### 3. Install the Python package

```bash
cd ..   # back to repo root
uv sync --all-groups   # installs all deps + dev deps, creates .venv
```

### 4. Configure

```bash
cp config/gateway.yaml config/my-gateway.yaml
# Edit the YAML — see Configuration section below
```

### 5. Run

```bash
# Validate config and print resolved settings (no connection made)
python -m gateway --config config/my-gateway.yaml --dry-run

# Run the gateway
python -m gateway --config config/my-gateway.yaml

# Or via the installed script
gateway --config config/my-gateway.yaml
```

---

## Configuration

All options live in `config/gateway.yaml`. Secrets can be overridden with environment variables:

| Env var | Config key |
|---|---|
| `GATEWAY_SFDI` | `device.sfdi` |
| `GATEWAY_PIN` | `device.pin` |
| `GATEWAY_CERT` | `device.cert` |

### Key fields

```yaml
device:
  sfdi: "111115"                     # Short-Form Device Identifier
  cert: "config/certs/device.pem"    # Device certificate (PEM)
  ca_dir: "config/certs/ca/"         # Trusted CA directory
  pin: "111115"                      # In-band registration PIN (optional)

server:
  interface: "eth0"                  # Network interface
  uri: "https://192.168.1.100/sep2"  # 2030.5 server URI
  command: "all"                     # register | all | metering | fsa

protocol:
  type: modbus                       # modbus | dnp3
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:
      active_power: 40100            # opModFixedW / opModTargetW
      reactive_power: 40101         # opModFixedVar / opModTargetVar
      max_power_limit: 40102        # opModMaxLimW
      ramp_time: 40103              # rampTms (1/100 s)
      connect: 40104                # opModConnect
      energize: 40105               # opModEnergize

logging:
  level: INFO
  format: text                      # text | json
```

---

## Project Structure

```
2030_5-client/
├── epri_client/              # EPRI C client (modified)
│   ├── Makefile              # Linux build (replaces bash4-dependent build.sh)
│   ├── der_client.c          # patched: emits EVENT_JSON: lines on DER events
│   └── build/client_test     # compiled binary (after make)
│
├── gateway/                  # Python package
│   ├── __main__.py           # entry point: python -m gateway
│   ├── config.py             # YAML loading, validation, dataclasses
│   ├── client.py             # subprocess wrapper for client_test
│   ├── bridge.py             # DERControl events → field protocol writes
│   ├── settings.py           # generates settings/*.xml from live device state
│   ├── log.py                # structured logging setup
│   └── protocols/
│       ├── __init__.py       # FieldProtocol abstract base
│       ├── modbus.py         # pymodbus adapter
│       └── dnp3.py           # DNP3 stub (not yet implemented)
│
├── tests/
│   ├── conftest.py           # shared fixtures
│   ├── test_config.py
│   ├── test_bridge.py
│   ├── test_client.py
│   ├── test_settings.py
│   └── protocols/
│       └── test_modbus.py
│
├── config/
│   ├── gateway.yaml          # example configuration
│   └── certs/                # certificate storage (gitignored)
│
├── Dockerfile                # Linux build env + runtime
└── pyproject.toml
```

---

## Running Tests

```bash
uv sync --all-groups
uv run pytest
```

Tests use mocks for the C binary and Modbus client — no hardware required.

---

## Implementing a New Field Device

1. **Read device state** — poll your device at startup and populate `DERState` in [`gateway/__main__.py`](gateway/__main__.py) before calling `write_settings()`. This sends capability, settings, status, and availability to the server.

2. **Apply controls** — extend `DERBridge._relinquish()` in [`gateway/bridge.py`](gateway/bridge.py) for your device's relinquish semantics. The `_apply_control()` method maps the standard 2030.5 control fields to register writes automatically.

3. **Meter readings** — add live meter reads before the `se_post()` calls in `epri_client/client_test.c` (search for `post_readings`). Replace the hardcoded values with actual Modbus reads.

4. **Add a new protocol** — implement `FieldProtocol` in `gateway/protocols/` and add the factory case in `gateway/bridge.py:make_bridge()`.

---

## How the C Patch Works

`epri_client/der_client.c` was modified to emit one JSON line per DER event to stdout:

```
EVENT_JSON:{"type":"start","sfdi":111115,"mrid":"0102...","description":"Curtail","control":{"opModFixedW":-50,"rampTms":100}}
EVENT_JSON:{"type":"end","sfdi":111115,"mrid":"0102...","description":"Curtail"}
```

`gateway/client.py` spawns the binary, reads stdout line-by-line, and yields parsed dicts for any line starting with `EVENT_JSON:`. All other C output (debug prints) passes through to stderr.

---

## References

- [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client)
- [IEEE 2030.5 Standard](https://standards.ieee.org/standard/2030_5-2018.html)
- [CSIP (Common Smart Inverter Profile)](https://sunspec.org/csip/)
- [pymodbus documentation](https://pymodbus.readthedocs.io/)

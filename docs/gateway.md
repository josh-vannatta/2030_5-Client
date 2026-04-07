# Gateway — Classes & Runtime Reference

The `gateway/` package is an IEEE 2030.5 DER control bridge. It connects a 2030.5-compliant server (managed by the EPRI `client_test` C binary) to field devices over Modbus TCP or DNP3. At startup it reads live device state, writes it into XML files the C binary consumes, then enters an event loop that translates `DERControl` commands into field-protocol register writes.

---

## Directory Layout

```
gateway/
├── __init__.py
├── __main__.py          ← entry point
├── bridge.py            ← DERBridge
├── client.py            ← EpriClient, EpriClientError
├── config.py            ← Config, ModbusConfig, Dnp3Config, RegisterMap, ReadMap, LogConfig
├── device.py            ← read_device_state()
├── log.py               ← _JsonFormatter, configure()
├── settings.py          ← DERState, write_settings()
└── protocols/
    ├── __init__.py      ← FieldProtocol (ABC)
    ├── modbus.py        ← ModbusAdapter
    └── dnp3.py          ← Dnp3Adapter (stub)
```

---

## Classes

### `Config` — `config.py`

Root configuration object, populated from a YAML file with optional environment-variable overrides (`GATEWAY_SFDI`, `GATEWAY_PIN`, `GATEWAY_CERT`).

| Field | Type | Description |
|---|---|---|
| `interface` | `str` | Network interface (e.g. `eth0`) |
| `server_uri` | `str` | 2030.5 server base URI |
| `cert` | `str` | Device certificate path (PEM) |
| `ca_dir` | `str` | CA certificates directory |
| `sfdi` | `str` | Short-Form Device Identifier |
| `command` | `str` | Startup command passed to `client_test` (default `"all"`) |
| `pin` | `str \| None` | In-band registration PIN |
| `protocol` | `"modbus" \| "dnp3"` | Field protocol to use |
| `modbus` | `ModbusConfig \| None` | Modbus-specific config |
| `dnp3` | `Dnp3Config \| None` | DNP3-specific config |
| `log` | `LogConfig` | Logging configuration |

**`validate()`** — raises `ValueError` if required fields are missing, cert/ca_dir paths don't exist, or the selected protocol has no corresponding config block.

**Module helpers**: `load(path)` → `Config`, `_apply_env_overrides(raw)`, `_build(raw)`.

---

### `ModbusConfig` — `config.py`

Modbus TCP connection parameters.

| Field | Default | Description |
|---|---|---|
| `host` | — | Target host |
| `port` | `502` | TCP port |
| `unit_id` | `1` | Modbus unit ID |
| `timeout` | `5.0` | Connection timeout (s) |
| `registers` | `RegisterMap()` | Write-register addresses |
| `reads` | `ReadMap()` | Read-register addresses |

---

### `RegisterMap` — `config.py`

Modbus holding-register addresses for DER control outputs. Each field maps a 2030.5 control attribute to a register address.

| Field | Default | 2030.5 Attribute |
|---|---|---|
| `active_power` | `40100` | `opModFixedW` / `opModTargetW` (signed %) |
| `reactive_power` | `40101` | `opModFixedVar` / `opModTargetVar` |
| `max_power_limit` | `40102` | `opModMaxLimW` (unsigned %) |
| `ramp_time` | `40103` | `rampTms` (1/100 s) |
| `connect` | `40104` | `opModConnect` (0 = disconnect, 1 = connect) |
| `energize` | `40105` | `opModEnergize` (0 = de-energize, 1 = energize) |

---

### `ReadMap` — `config.py`

Optional Modbus input-register addresses for telemetry reads at startup. All fields default to `None`; unset fields are skipped gracefully.

Categories: status/availability (`inverter_status`, `gen_connect_status`, `state_of_charge`, `available_w`, `available_var`), static capability (`rated_w`, `rated_va`, `rated_ah`), operator limits (`max_w`, `max_a`), and metering (`active_power_output`, `reactive_power_output`, `energy_delivered_wh`).

---

### `Dnp3Config` — `config.py`

DNP3 connection parameters (`host`, `port`, `master_address`, `outstation_address`). Reserved for future use; corresponding adapter raises `NotImplementedError`.

---

### `LogConfig` — `config.py`

Logging settings: `level`, `format` (`"json"` or `"text"`), and optional `file` path.

---

### `DERState` — `settings.py`

Snapshot of DER device state in IEEE 2030.5 units. Populated from field-device register reads at startup; defaults are used for any register that fails or is not mapped.

| Category | Fields |
|---|---|
| Capability | `rtg_w`, `rtg_va`, `rtg_ah` |
| Settings | `set_max_w`, `set_max_a`, `set_es_high_volt`, `set_es_low_volt` |
| Status | `inverter_status`, `state_of_charge`, `gen_connect_status` |
| Availability | `stat_w_avail`, `stat_var_avail` |

**`write_settings(state, directory)`** — writes four XML files (`DERCapability.xml`, `DERSettings.xml`, `DERStatus.xml`, `DERAvailability.xml`) into the given directory for the C binary to read at launch.

---

### `FieldProtocol` — `protocols/__init__.py`

Abstract base class defining the interface all field-protocol adapters must implement.

| Method | Description |
|---|---|
| `connect()` | Open connection to field device |
| `disconnect()` | Close connection |
| `write_register(address, value)` | Write a 16-bit holding register |
| `read_register(address) → int` | Read a 16-bit holding register |

Supports use as a context manager (`__enter__` / `__exit__`).

---

### `ModbusAdapter` — `protocols/modbus.py`

Implements `FieldProtocol` for Modbus TCP via `pymodbus`. Wraps `ModbusTcpClient`; enforces a connected-state guard before every read/write.

---

### `Dnp3Adapter` — `protocols/dnp3.py`

Stub implementing `FieldProtocol` for DNP3. All methods raise `NotImplementedError`. Exists so the factory pattern in `bridge.py` remains protocol-agnostic.

---

### `DERBridge` — `bridge.py`

Translates IEEE 2030.5 `DERControl` events into field-protocol register writes. This is the core runtime object.

**Constructor**: `DERBridge(protocol: FieldProtocol, registers: RegisterMap)`

**`apply(event)`** — dispatches on event type:

| Event type | Action |
|---|---|
| `"start"` | Apply new DERControl setpoints |
| `"end"` | Relinquish control — clear all registers written during the event |
| `"default_control"` | Apply server-specified fallback setpoints |

Internally tracks every register address written during the active event in `_active_registers` so `_relinquish()` can zero them out cleanly.

**2030.5 → register mapping** (inside `_apply_control`):

| 2030.5 field | Register |
|---|---|
| `opModFixedW` | `active_power` |
| `opModTargetW` | `active_power` (takes precedence over `FixedW`) |
| `opModMaxLimW` | `max_power_limit` |
| `opModFixedVar` / `opModTargetVar` | `reactive_power` |
| `rampTms` | `ramp_time` |
| `opModConnect` | `connect` |
| `opModEnergize` | `energize` |

**`make_bridge(config)`** — factory function that instantiates the correct adapter and returns a `DERBridge`.

---

### `EpriClient` — `client.py`

Manages the lifecycle of the EPRI `client_test` subprocess and exposes its event stream.

**Constructor**: `EpriClient(config: Config, binary: Path | str | None = None)`

Binary defaults to `core/build/client_test`.

| Method | Description |
|---|---|
| `start()` | Spawn subprocess with args built from `Config` |
| `stop()` | Graceful terminate (5 s timeout), then `kill()` |
| `events()` | Iterator yielding parsed JSON dicts from stdout lines prefixed `EVENT_JSON:` |

Supports use as a context manager. Non-event stdout lines are logged at DEBUG.

---

### `EpriClientError` — `client.py`

Custom exception raised on subprocess errors.

---

### `_JsonFormatter` — `log.py`

`logging.Formatter` subclass that serialises log records as single-line JSON with fields: `ts`, `level`, `logger`, `msg`, and `exc` (when an exception is present).

**`configure(level, fmt, file)`** — module-level function that wires up the root logger once at startup.

---

## Runtime Data Flow

### Startup

```
YAML file
  └─→ config.load()
        └─→ Config (validated)
              ├─→ log.configure()
              ├─→ make_bridge()  →  ModbusAdapter / Dnp3Adapter
              ├─→ read_device_state(protocol, reads)
              │     └─→ FieldProtocol.read_register() × N
              │           └─→ DERState
              └─→ write_settings(state, "core/settings/")
                    └─→ DERCapability.xml
                        DERSettings.xml
                        DERStatus.xml
                        DERAvailability.xml
```

### Event loop

```
EpriClient.start()  →  client_test subprocess
  └─→ EpriClient.events()
        └─→ stdout line "EVENT_JSON: {...}"
              └─→ dict
                    └─→ DERBridge.apply(event)
                          └─→ _apply_control() / _relinquish()
                                └─→ FieldProtocol.write_register()
                                      └─→ Field device (inverter / DER)
```

---

## Entry Point — `__main__.py`

`main(argv)` orchestrates the full lifecycle:

1. Parse `--config` and `--dry-run` args
2. `config.load()` — load and validate YAML
3. `log.configure()` — set up logging
4. `--dry-run` — print config and exit `0`
5. `make_bridge()` — create protocol adapter + bridge
6. Connect protocol, read device state, write XML settings
7. Launch `EpriClient`, iterate `events()`, call `bridge.apply()` for each
8. Return `0` on clean exit, `1` on error

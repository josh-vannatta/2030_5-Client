# Architecture

The IEEE 2030.5 DER Gateway is a Python process that sits between an IEEE 2030.5 utility server and one or more field devices (inverters, batteries, controllable loads). It has two hard boundaries: **northbound** to the 2030.5 server, and **southbound** to field devices over Modbus TCP or DNP3.

See [system_overview](architecture/system_overview.mermaid) for the top-level block diagram.

---

## Process Boundary

The gateway runs as **two cooperating processes**:

### C Binary (`core/build/client_test`)

The [EPRI IEEE 2030.5 Client](https://github.com/epri-dev/IEEE-2030.5-Client), with a small patch. It owns the full 2030.5 stack:

- TLS 1.2 with mutual auth (ECDSA P-256, `TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8`)
- EXI encoding/decoding (Efficient XML Interchange — compact binary XML)
- 2030.5 resource discovery and traversal
- DERControl event scheduling (start time, duration, priority, randomization)
- Certificate-based device identity (SFDI embedded in cert Subject)

The C binary is Linux-only — it uses `epoll` and cannot compile on macOS. On macOS, use Docker or the VS Code Dev Container.

### Python Gateway (`gateway/`)

Handles everything outside the 2030.5 wire protocol:

- Reads `gateway.yaml` and validates all config at startup
- Reads live device state from the field device over Modbus
- Generates the four 2030.5 XML settings files before spawning the C binary
- Spawns the C binary as a subprocess
- Parses `EVENT_JSON:` lines from the C binary's stdout
- Translates DER events to Modbus register writes
- Tracks active registers for clean relinquish on event end

See [component_map](architecture/component_map.mermaid) for the Python module dependency graph.

---

## IPC: The `EVENT_JSON:` Protocol

The only channel from C → Python is **stdout**. The C patch adds a sentinel line for each DER event transition:

```
EVENT_JSON:{"type":"start","mrid":"abc123","start":1700000000,"duration":900,"control":{"opModFixedW":8000,"rampTms":60}}
EVENT_JSON:{"type":"end","mrid":"abc123"}
EVENT_JSON:{"type":"default_control","control":{"opModMaxLimW":10000,"opModConnect":true}}
```

`gateway/client.py` reads stdout line-by-line; lines starting with `EVENT_JSON:` are parsed as JSON and yielded. All other C output (TLS handshake status, poll logs) goes to stderr.

This one-way pipe keeps the two processes loosely coupled — the C binary needs no knowledge of the field protocol or register map.

---

## Data Flows

See [data_model](architecture/data_model.mermaid) for the full type-level data flow. Summary:

### Northbound (device → server)

At startup, `device.read_device_state()` reads telemetry registers from the field device and builds a `DERState` dataclass. `settings.write_settings()` converts this to four XML files (`DERCapability`, `DERSettings`, `DERStatus`, `DERAvailability`) that the C binary reads before connecting to the server.

```
Modbus reads → DERState → XML files → C binary reads → PUT to server
```

### Southbound (server → device)

The server pushes DERControl events to the C binary, which schedules them and emits `EVENT_JSON:` lines at the correct start time. `bridge.DERBridge.apply()` maps the `DERControlBase` fields to register addresses from `RegisterMap` and writes them over Modbus. On event end, `_relinquish()` writes 0 to every register that was set.

```
Server pushes DERControl → C schedules → EVENT_JSON: stdout → bridge.apply() → Modbus writes
```

---

## Startup Sequence

See [startup_sequence](sequence/startup_sequence.mermaid) for the full interaction diagram. See [event_start_end](sequence/event_start_end.mermaid) and [event_default_control](sequence/event_default_control.mermaid) for the event lifecycle.

1. Load and validate `gateway.yaml`
2. Connect to Modbus device
3. Read all `reads.*` registers → build `DERState`
4. Write XML settings files
5. Spawn `client_test` subprocess
6. C binary reads XML, loads certs, connects to server
7. 2030.5 resource discovery: `/dcap` → `/edev/{sfdi}` → `/fsa` → `/derp` → `/derc`
8. C binary PUTs capabilities to server
9. C binary subscribes to DERControl notifications
10. Python bridge enters event loop — applies events as they arrive

---

## 2030.5 Resource Graph

See [process/2030_5_resource_traversal](process/2030_5_resource_traversal.mermaid) for the full resource navigation map, and [sequence/2030_5_resource_traversal](sequence/2030_5_resource_traversal.mermaid) for the EXI-encoded HTTP exchange detail.

The SFDI (`{sfdi}` in URLs) is a 36-bit value derived from the device certificate's SHA-256 fingerprint. Run `scripts/gen_dev_certs.py` to generate certs and compute the SFDI — it auto-writes the value to `gateway.yaml`.

---

## Field Protocol Abstraction

`gateway/protocols/base.py` defines a `FieldProtocol` abstract base class. `bridge.py`, `device.py`, and (in Phase 2) `telemetry.py` all depend on this interface, not on Modbus directly. Adding a new protocol means implementing `FieldProtocol` — the rest of the gateway is unchanged.

Current adapters:

| Adapter | Status | Notes |
|---------|--------|-------|
| `protocols/modbus.py` | ✅ | pymodbus TCP, unit-tested with mocks |
| `protocols/dnp3.py` | ⬜ Phase 3 | Stub — raises `NotImplementedError` |

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ | Foundation: config, bridge, device read, XML gen, subprocess, tests |
| 1 | ⬜ | Live telemetry: periodic Modbus → DERStatus/Availability PUT; meter reads |
| 2 | ⬜ | Resilience: process supervision, Modbus reconnect, health endpoint |
| 3 | ⬜ | DNP3: implement `Dnp3Adapter` |

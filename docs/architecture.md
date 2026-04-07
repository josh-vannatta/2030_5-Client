# Architecture

The IEEE 2030.5 DER Gateway is a two-process integration layer that bridges an IEEE 2030.5 utility server to field devices over Modbus TCP today and DNP3 later. It has two hard boundaries:

- **Northbound:** IEEE 2030.5 server
- **Southbound:** field device protocol adapter :contentReference[oaicite:0]{index=0}

At a high level, the C client owns the IEEE 2030.5 wire protocol, while the Python gateway owns field integration, configuration, and runtime control translation. :contentReference[oaicite:1]{index=1}

## System context

> Diagram: [01_system_overview.mermaid](architecture/01_system_overview.mermaid)

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

## Process boundary

The gateway is intentionally split into two cooperating processes.

### C client (`core/build/client_test`)

The patched EPRI IEEE 2030.5 Client owns the full IEEE 2030.5 stack:

* TLS 1.2 with mutual authentication
* EXI encoding and decoding
* 2030.5 resource discovery and traversal
* DERControl scheduling
* certificate-based device identity 

This binary is Linux-only because it uses `epoll`. On macOS, development and execution must happen inside Docker or the VS Code Dev Container.  

### Python gateway (`gateway/`)

The Python side handles everything outside the 2030.5 transport:

* loading and validating `gateway.yaml`
* reading startup device state from the field device
* generating the 2030.5 XML settings files
* spawning and supervising the C subprocess
* parsing `EVENT_JSON:` lines from stdout
* translating DER events to field-protocol register writes
* tracking active registers for relinquish on event end 

## Module layout

> Diagram: [02_component_map.mermaid](architecture/02_component_map.mermaid)

The Python package is structured around a small set of focused modules:

```text
gateway/
├── __main__.py       # Entry point: orchestrates startup and event loop
├── config.py         # YAML -> typed config + validation + env overrides
├── client.py         # EpriClient subprocess wrapper and EVENT_JSON parser
├── bridge.py         # DERControlBase -> RegisterMap -> field writes
├── device.py         # Startup telemetry reads -> DERState
├── settings.py       # DERState -> DERCapability/Settings/Status/Availability XML
├── log.py            # Text / JSON logging setup
└── protocols/
    ├── __init__.py   # FieldProtocol abstraction
    ├── modbus.py     # Modbus TCP adapter
    └── dnp3.py       # Planned / stub
```

This package boundary reflects the current runtime responsibilities and matches both the code reference and the development guide.  

## IPC contract: `EVENT_JSON:`

The only channel from C to Python is stdout. The patched C client emits one sentinel line per DER event transition:

```text
EVENT_JSON:{"type":"start","mrid":"abc123","start":1700000000,"duration":900,"control":{"opModFixedW":8000,"rampTms":60}}
EVENT_JSON:{"type":"end","mrid":"abc123"}
EVENT_JSON:{"type":"default_control","control":{"opModMaxLimW":10000,"opModConnect":true}}
```

`gateway/client.py` reads stdout line-by-line. Lines beginning with `EVENT_JSON:` are parsed as JSON and yielded into the Python event loop; non-event output is treated as ordinary process output. This keeps the C binary isolated from field protocol details and register maps. 

## Northbound and southbound flows

> Diagram: [03_data_model.mermaid](architecture/03_data_model.mermaid)

The gateway has two primary data flows.

### Northbound: device → server

At startup, the Python gateway reads telemetry and capability values from the field device, builds a `DERState`, converts that into four XML settings files, and lets the C client upload those resources to the server.  

Flow:

```text
Modbus reads
  → DERState
  → DERCapability.xml
  → DERSettings.xml
  → DERStatus.xml
  → DERAvailability.xml
  → C client reads XML
  → PUT to 2030.5 server
```

### Southbound: server → device

The server sends DERControl information to the C client. The C client handles scheduling and emits `EVENT_JSON:` at the correct transition points. The Python bridge maps the control fields onto protocol register addresses and writes them to the field device. On event end, the gateway relinquishes registers by writing zero to the tracked addresses.  

Flow:

```text
2030.5 server
  → DERControl
  → C client scheduling
  → EVENT_JSON stdout
  → DERBridge.apply()
  → register map lookup
  → Modbus writes
  → field device
```

## Startup sequence

The startup flow is intentionally simple and linear:

1. load and validate `gateway.yaml`
2. configure logging
3. construct the field-protocol adapter and bridge
4. connect to the field device
5. read startup registers and build `DERState`
6. write XML settings files
7. spawn `client_test`
8. let the C client perform resource discovery
9. subscribe to DERControl notifications
10. enter the Python event loop   

A key architectural constraint in the current implementation is that the XML settings files are written once at startup and not refreshed during steady state. 

## 2030.5 resource traversal

> Diagram: [p0_resource_traversal.mermaid](architecture/04_resource_traversal.mermaid)

After startup, the C client performs standard 2030.5 discovery and traversal. The documented traversal path is:

```text
GET /dcap
  → GET /tm
  → GET /edev/{sfdi}
  → GET /edev/{sfdi}/fsa
  → GET /edev/{sfdi}/fsa/derp
  → GET /edev/{sfdi}/fsa/derp/{id}/dderc
  → GET /edev/{sfdi}/fsa/derp/{id}/derc
  → POST subscription
  → PUT DER resources
```

This is the conceptual resource graph reflected in the existing architecture and sequence documentation. 

The SFDI in those resource paths is derived from the device certificate rather than manually chosen. The development and configuration guides both note that `scripts/gen_dev_certs.py` generates certificates, computes the SFDI, and writes it back into `gateway.yaml`.  

## Field protocol abstraction

The Python side is designed so that gateway logic depends on a protocol interface rather than on Modbus directly. `FieldProtocol` defines the abstract operations required by the gateway, and `bridge.py`, `device.py`, and future telemetry components work against that abstraction.  

Current adapters:

| Adapter               | Status      | Notes                               |
| --------------------- | ----------- | ----------------------------------- |
| `protocols/modbus.py` | implemented | `pymodbus` TCP adapter              |
| `protocols/dnp3.py`   | stub        | raises `NotImplementedError` today  |

This means protocol expansion should primarily require implementing a new adapter and wiring it into configuration and startup, not rewriting the bridge or device-state logic. 

## Key architectural decisions

### Two-process model instead of a pure Python 2030.5 client

The design deliberately reuses the EPRI client for standards-facing protocol work and keeps Python focused on local integration. That reduces protocol implementation burden and keeps the field-integration layer easier to evolve. This division of responsibilities is explicit in the current architecture and runtime docs. 

### One-way IPC from C to Python

Using stdout `EVENT_JSON:` as the C→Python channel keeps the two layers loosely coupled. The C client does not need to know anything about the field protocol, register map, or device-specific control surface. 

### Startup snapshot instead of live telemetry loop

Phase 0 is designed around a startup-only telemetry snapshot. The initial capability, settings, status, and availability are captured once, written to XML, and consumed by the C client. Live telemetry updates are explicitly deferred to a later phase.  

## Current implementation scope

Implemented now:

* config loading and validation
* Modbus adapter
* startup device reads
* XML generation
* subprocess lifecycle management
* `EVENT_JSON` parsing
* DERControl translation and register writes
* relinquish on event end
* mocked test coverage  

Not implemented yet:

* live telemetry refresh after startup
* live meter readings from device values
* process restart and supervision
* DNP3 implementation
* OpenFMB / MQTT / NATS integration 

## Class reference

The diagram at [`docs/architecture/05_gateway_classes.mermaid`](architecture/05_gateway_classes.mermaid) shows every class in `gateway/`. A summary of each class and its role:

| Class | Module | Kind | Role |
|---|---|---|---|
| `Config` | `config.py` | dataclass | Top-level config object; validated at load time; passed to `EpriClient` and `make_bridge()` |
| `ModbusConfig` | `config.py` | dataclass | Modbus TCP host/port/timeout plus nested `RegisterMap` and `ReadMap` |
| `Dnp3Config` | `config.py` | dataclass | DNP3 host/port and master/outstation addresses |
| `LogConfig` | `config.py` | dataclass | Log level, format (`json`/`text`), and optional file path |
| `RegisterMap` | `config.py` | dataclass | Holding-register addresses used for control writes (opModFixedW, opModConnect, …) |
| `ReadMap` | `config.py` | dataclass | Input-register addresses for startup telemetry reads; `None` fields are skipped |
| `DERState` | `settings.py` | dataclass | Snapshot of device telemetry and ratings produced by `read_device_state()`; consumed by XML writers |
| `FieldProtocol` | `protocols/__init__.py` | ABC | Protocol interface: `connect`, `disconnect`, `write_register`, `read_register`; also a context manager |
| `ModbusAdapter` | `protocols/modbus.py` | class | Concrete `FieldProtocol` over Modbus TCP via `pymodbus` |
| `Dnp3Adapter` | `protocols/dnp3.py` | class (stub) | Concrete `FieldProtocol` shell for DNP3; all methods raise `NotImplementedError` |
| `DERBridge` | `bridge.py` | class | Translates `EVENT_JSON` dicts into register writes; tracks active registers for relinquish on event end |
| `EpriClient` | `client.py` | class | Manages the `client_test` subprocess lifecycle and yields parsed event dicts from stdout |
| `EpriClientError` | `client.py` | exception | Raised by `EpriClient` on missing binary or non-zero subprocess exit |
| `_JsonFormatter` | `log.py` | class | `logging.Formatter` subclass that serialises log records as single-line JSON |

### Composition hierarchy

```text
Config
 ├── ModbusConfig
 │    ├── RegisterMap
 │    └── ReadMap
 ├── Dnp3Config
 └── LogConfig

DERBridge
 ├── FieldProtocol  (ModbusAdapter | Dnp3Adapter)
 └── RegisterMap

EpriClient
 └── Config
```

## Phase roadmap

The current architecture doc and repo summary point to a staged roadmap:

| Phase   | Status             | Description                                                                    |
| ------- | ------------------ | ------------------------------------------------------------------------------ |
| Phase 0 | implemented        | foundation: config, bridge, device read, XML generation, subprocess, tests     |
| Phase 1 | proposed           | live telemetry polling, updated DERStatus / DERAvailability, live meter reads  |
| Phase 2 | proposed           | resilience: restart loop, reconnects, health checks                            |
| Phase 3 | proposed           | DNP3 adapter implementation                                                    |
| Phase 4 | possible extension | OpenFMB / additional protocol integrations, if pursued                         |


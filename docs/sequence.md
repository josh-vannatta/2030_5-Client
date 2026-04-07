# Operations

At runtime, the gateway is a Python process that:

1. loads and validates configuration
2. connects to the configured field protocol
3. reads a startup device snapshot
4. writes four 2030.5 XML settings files
5. spawns the EPRI `client_test` subprocess
6. blocks on `EVENT_JSON:` lines from the C client
7. translates events into field-protocol register writes :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

A critical operational constraint in the current implementation is that the XML settings files are written **once at startup** and are not refreshed during steady-state operation. :contentReference[oaicite:4]{index=4}

## Lifecycle phases

The gateway progresses through four phases:

```text id="xehgw8"
INIT
  → STARTUP
  → EVENT LOOP
  → TEARDOWN
````

### 1. INIT

During INIT, `config.load()` parses `gateway.yaml`, applies environment variable overrides, validates paths and required fields, and raises immediately on invalid config. Logging is configured, and the field-protocol adapter plus `DERBridge` are instantiated, but no connection is opened yet. 

State after INIT:

* config is loaded and effectively immutable
* protocol adapter exists but is not connected
* bridge exists but has not written anything to the field device 

### 2. STARTUP

> Diagram: [01_startup_sequence.mermaid](sequence/01_startup_sequence.mermaid) — full INIT → STARTUP → first event delivery  
> Diagram: [02_resource_traversal.mermaid](sequence/02_resource_traversal.mermaid) — 2030.5 discovery and traversal detail

During STARTUP, the protocol adapter connects, startup reads are performed, the device snapshot is converted into `DERState`, and the four XML files are written into `core/settings/`. The C client is then started and immediately reads those XML files. 

State after STARTUP:

* field-protocol connection is open
* XML settings files exist on disk
* `client_test` is running
* the startup `DERState` object has already been discarded and is not kept as live state 

### 3. EVENT LOOP

> Diagram: [03_event_start_end.mermaid](sequence/03_event_start_end.mermaid) — start and end event flow  
> Diagram: [04_event_default_control.mermaid](sequence/04_event_default_control.mermaid) — default_control event flow

The Python gateway blocks on stdout from the C client. Each line prefixed with `EVENT_JSON:` is parsed and dispatched through `DERBridge.apply()`. During this phase, the main mutable runtime state is `_active_registers`, which tracks addresses written by the currently active control context.  

### 4. TEARDOWN

> Diagram: [05_teardown_sequence.mermaid](sequence/05_teardown_sequence.mermaid)

Teardown happens when the C subprocess exits, or when Python unwinds due to exception or interrupt. The gateway attempts graceful subprocess termination first, then forces termination if needed, and disconnects the field-protocol adapter during context-manager cleanup. 

Important caveat: if the gateway exits in the middle of an active event, the field device keeps the last written values. Registers are not automatically relinquished on crash or hard exit. 

## Event handling semantics

The event loop handles three event types:

| Event             | Gateway action                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------ |
| `start`           | Translate DERControl fields into register writes, track written addresses in `_active_registers` |
| `end`             | Write `0` to each tracked register, then clear `_active_registers`                               |
| `default_control` | Clear `_active_registers`, then apply the fallback control as a fresh write set                  |

This is the core operational behavior of `DERBridge.apply()`.  

### Control-to-register mapping

The bridge maps 2030.5 control fields onto configured register addresses:

| 2030.5 field                       | Register map key  |
| ---------------------------------- | ----------------- |
| `opModFixedW` / `opModTargetW`     | `active_power`    |
| `opModMaxLimW`                     | `max_power_limit` |
| `opModFixedVar` / `opModTargetVar` | `reactive_power`  |
| `rampTms`                          | `ramp_time`       |
| `opModConnect`                     | `connect`         |
| `opModEnergize`                    | `energize`        |

This mapping is implemented in the bridge and driven by `RegisterMap` from configuration. 

## Runtime state inventory

The gateway keeps a small amount of live runtime state.

| State                     | Location              | Lifetime           | Notes                                           |
| ------------------------- | --------------------- | ------------------ | ----------------------------------------------- |
| `Config`                  | `config.py`           | whole process      | loaded once, then read-only                     |
| field-protocol connection | protocol adapter      | startup → teardown | opened by `connect()`, closed by `disconnect()` |
| `EpriClient._proc`        | `client.py`           | startup → teardown | subprocess handle                               |
| `DERState`                | `settings.py`         | startup only       | used to write XML, then discarded               |
| XML settings files        | `core/settings/*.xml` | written at startup | read by C client                                |
| `_active_registers`       | `bridge.py`           | event loop         | mutable active-control state                    |

This is the operationally important distinction: most state is static or startup-only; `_active_registers` is the main state that changes during runtime. 

### `_active_registers` lifecycle

```text id="a2sdl1"
{} (empty)
  → start / default_control
  → {addr: value, ...}
  → end
  → write 0 to each tracked address
  → {}
```

The key nuance is that `default_control` clears `_active_registers` and then writes the fallback values as a new control set. That means a later `end` only relinquishes the registers associated with the most recent active control set. 

## Failure behavior

> Diagram: [06_failure_modes.mermaid](sequence/06_failure_modes.mermaid)

Operationally, the gateway fails in a few distinct ways.

| Failure point                       | Behavior                                              |
| ----------------------------------- | ----------------------------------------------------- |
| bad `gateway.yaml`                  | config load raises; process exits before connecting   |
| missing cert or CA path             | validation fails during startup                       |
| startup register read failure       | warning logged; default value used; startup continues |
| register write failure during event | exception logged and propagated                       |
| `client_test` exits non-zero        | `EpriClientError` raised after stdout closes          |
| `client_test` binary missing        | `EpriClientError` raised on startup                   |

These behaviors are part of the current runtime contract and matter for operations and troubleshooting. 

## Operational caveats

### XML is startup-only in Phase 0

The XML files in `core/settings/` are written only during startup. They are not treated as a continuously updated state channel during steady-state operation. 

### Crash does not auto-relinquish

If the process dies during an active event, previously written field-device setpoints remain in effect until something else changes them. There is no automatic crash-time relinquish. 

## Wire-protocol detail

The following diagrams cover the northbound protocol stack below the Python/C boundary. They are not needed to operate the gateway but are useful for debugging TLS or EXI issues.

| Diagram | What it shows |
|---|---|
| [07_tls_packet_exchange.mermaid](sequence/07_tls_packet_exchange.mermaid) | Full TLS 1.2 mutual-auth handshake: ClientHello → CertificateVerify → session keys |
| [08_exi_encoding.mermaid](sequence/08_exi_encoding.mermaid) | EXI encode/decode path: C struct → EXI codec → TLS → server response |


## Documentation
* [../README.md](Readme.md) — overview, quickstart, repo map
* [architecture.md](docs/architecture.md) — system boundaries, process model, IPC, data flows
* [configuration.md](docs/configuration.md) — app configuration, environment variables, 
* [sequence.md](docs/sequence.md) — lifecycle, runtime state, configuration, failure behavior
* [development.md](docs/development.md) — setup, testing, certificates, extension workflow

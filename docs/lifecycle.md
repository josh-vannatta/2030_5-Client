# Gateway — Lifecycle & State Management

This document describes how the Python gateway progresses through its lifecycle phases and what state exists at each point.

---

## Lifecycle Phases

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   INIT       │ →  │   STARTUP    │ →  │  EVENT LOOP  │ →  │  TEARDOWN    │
│ load config  │    │ read device  │    │ apply events │    │ stop process │
│ build bridge │    │ write XML    │    │ write regs   │    │ disconnect   │
│              │    │ spawn binary │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### 1. INIT — `__main__.main()`

- `config.load()` parses `gateway.yaml`, applies environment variable overrides (`GATEWAY_SFDI`, `GATEWAY_PIN`, `GATEWAY_CERT`), and validates paths and required fields. Raises on any error — the process does not start with a bad config.
- `log.configure()` sets up the root logger.
- `make_bridge()` instantiates the field-protocol adapter (`ModbusAdapter` or `Dnp3Adapter`) and the `DERBridge`, but does **not** open a connection yet.

State after INIT: `Config` is frozen. `DERBridge` and its adapter exist but are not connected.

### 2. STARTUP — inside `with bridge.protocol:`

The protocol adapter's `connect()` is called on context manager entry.

- `read_device_state(protocol, reads)` polls every register address listed in `ReadMap`. Failed or unmapped reads fall back to `DERState` defaults — a single bad register does not abort startup.
- The resulting `DERState` snapshot is passed to `write_settings()`, which overwrites four XML files in `core/settings/`. This is the **only time** the gateway writes those files.
- `EpriClient.start()` then spawns `client_test`, passing the server URI, cert paths, SFDI, and interface via CLI arguments. The C binary reads the XML files immediately on startup; the Python side does not touch them again.

State after STARTUP: `DERState` is discarded after XML is written — it is a one-shot initialiser, not kept in memory. The only live state from this phase is `EpriClient._proc` (the subprocess handle).

### 3. EVENT LOOP — `for event in client.events()`

The gateway blocks reading `client_test` stdout. Each `EVENT_JSON:` line is parsed and dispatched through `DERBridge.apply()`.

There are three event types:

| Event | Gateway action |
|---|---|
| `start` | Translate DERControl fields to register writes via `_apply_control()`. Record every written address in `_active_registers`. |
| `end` | Call `_relinquish()`: write `0` to every address in `_active_registers`, then clear the dict. The device reverts to internal control until the next `default_control` event arrives. |
| `default_control` | Clear `_active_registers`, then apply the server's fallback setpoints. Treated as a fresh write, not a relinquish. |

Non-`EVENT_JSON:` stdout lines are forwarded to the logger at DEBUG level.

### 4. TEARDOWN

Normal teardown happens when `client_test` exits (closes its stdout). `EpriClient.events()` calls `_proc.wait()` and raises `EpriClientError` if the exit code is non-zero.

On exception or `KeyboardInterrupt`, Python's context manager unwinding calls:
1. `EpriClient.__exit__` → `stop()` (SIGTERM, 5 s timeout, then SIGKILL)
2. `bridge.protocol.__exit__` → `disconnect()`

The register state on the field device is whatever was last written. If the gateway exits mid-event the device retains the last setpoints; `_relinquish()` is not called automatically on crash.

---

## State Inventory

| State | Location | Lifetime | Mutated by |
|---|---|---|---|
| `Config` | `config.py · Config` dataclass | Entire process; read-only after `load()` | `load()` once at startup |
| Field-protocol connection | `protocols/modbus.py · ModbusTcpClient` | Init → teardown | `connect()` / `disconnect()` |
| `EpriClient._proc` | `client.py` | Startup → teardown | `start()` / `stop()` |
| `DERState` | `settings.py · DERState` | Startup only; discarded after `write_settings()` | `read_device_state()` |
| XML settings files | `core/settings/*.xml` | Written once at startup; read by C binary | `write_settings()` |
| `DERBridge._active_registers` | `bridge.py · DERBridge` | Event loop | `_apply_control()` on `start` / `default_control`; `_relinquish()` on `end` |

The only state that changes during normal runtime is `_active_registers`. Everything else is either set once and held constant (`Config`, connection, subprocess handle) or produced and thrown away (`DERState`, XML files).

---

## `_active_registers` State Transitions

```
                  ┌─────────────────────┐
                  │  {} (empty)         │  ← initial / after relinquish
                  └──────────┬──────────┘
                             │
              EVENT: start   │   or   EVENT: default_control
              ───────────────▼──────────────────────────────
                  ┌─────────────────────┐
                  │  {addr: value, ...} │  ← registers owned by active event
                  └──────────┬──────────┘
                             │
              EVENT: end     │
              (writes 0 to each address, then clears)
              ───────────────▼───────────────────────
                  ┌─────────────────────┐
                  │  {} (empty)         │
                  └─────────────────────┘
```

A `default_control` event first clears `_active_registers` before writing, so if a `default_control` arrives without a preceding `end`, the previously tracked addresses are released from tracking (though their register values are overwritten, not zeroed). A subsequent `end` will then only relinquish the registers written by the `default_control`.

---

## Error Behaviour

| Failure point | Behaviour |
|---|---|
| Bad `gateway.yaml` | `config.load()` raises; process exits `1` before connecting to anything |
| Cert / CA path missing | Same — caught in `Config.validate()` |
| Register read fails at startup | Warning logged; `DERState` default used; startup continues |
| Register write fails during event | Exception logged and re-raised from `DERBridge._write()`; propagates up through `events()` loop |
| `client_test` exits non-zero | `EpriClientError` raised from `events()` after stdout closes |
| `client_test` binary not found | `EpriClientError` raised from `start()` before subprocess is created |

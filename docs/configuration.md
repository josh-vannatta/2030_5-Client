# Configuration Reference

All configuration lives in a single YAML file (default: `config/gateway.yaml`). Pass an alternate path with `--config <path>`.

Secrets can be injected via environment variables — they override the corresponding YAML field:

| Env var | YAML key | Notes |
|---------|----------|-------|
| `GATEWAY_SFDI` | `device.sfdi` | Override SFDI without editing the file |
| `GATEWAY_PIN` | `device.pin` | In-band registration PIN |
| `GATEWAY_CERT` | `device.cert` | Path to device certificate |

---

## `device`

Identity and certificate configuration for this DER device.

```yaml
device:
  sfdi: "320841683177"
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sfdi` | string | yes | 36-bit device identifier (decimal). Derived from certificate — run `scripts/gen_dev_certs.py` to compute. |
| `cert` | path | yes | PEM file containing the device's ECDSA P-256 certificate and private key. Validated at startup. |
| `ca_dir` | path | yes | Directory containing trusted CA certificate(s) (`ca.pem`). Used for server cert verification. |
| `pin` | string | no | In-band registration PIN. Only needed if the server requires device self-registration via `POST /edev`. |

**SFDI generation:** The SFDI is computed as `SHA-256(pem_bytes)[:5_bytes] >> 4`, then a check digit is appended. Running `scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml` generates certs and writes the computed SFDI directly into `gateway.yaml`. If you replace the cert, re-run the script.

---

## `server`

Connection parameters for the IEEE 2030.5 utility server.

```yaml
server:
  interface: "eth0"
  uri: "https://192.168.1.100/sep2"
  command: "all"
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interface` | string | yes | Network interface to bind for outbound connections (passed to C binary). |
| `uri` | string | yes | Base URI of the 2030.5 server. All resource paths (`/dcap`, `/edev/...`) are appended to this. |
| `command` | string | yes | C binary operation mode: `all` (full stack), `register` (self-register only), `fsa` (function set assignments only), `metering` (metering only). Use `all` for normal operation. |

---

## `protocol`

Field device connection and register map.

```yaml
protocol:
  type: modbus
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:
      active_power:    40100
      reactive_power:  40101
      max_power_limit: 40102
      ramp_time:       40103
      connect:         40104
      energize:        40105
    reads:
      inverter_status:     30201
      gen_connect_status:  30202
      state_of_charge:     30200
      available_w:         30203
      available_var:       30204
      rated_w:             30300
      rated_va:            30301
      rated_ah:            30302
      max_w:               30303
      max_a:               30304
```

### `protocol.type`

`modbus` (default). `dnp3` is planned (Phase 3) — raises `NotImplementedError` today.

### `protocol.modbus`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `host` | string | yes | IP address or hostname of the Modbus TCP device. |
| `port` | int | no | Modbus TCP port. Default: `502`. |
| `unit_id` | int | no | Modbus unit (slave) ID. Default: `1`. |

### `protocol.modbus.registers` (write map)

Maps semantic DER control names to Modbus holding register addresses. These registers are **written** when a DERControl event arrives and **zeroed** when the event ends (`_relinquish()`).

| Key | DER field | Notes |
|-----|-----------|-------|
| `active_power` | `opModFixedW`, `opModTargetW` | Watts |
| `reactive_power` | `opModFixedVar` | VAR |
| `max_power_limit` | `opModMaxLimW` | Watts |
| `ramp_time` | `rampTms` | Milliseconds |
| `connect` | `opModConnect` | `1` = connect, `0` = disconnect |
| `energize` | `opModEnergize` | `1` = energize |

Only registers explicitly listed here are written. If a DERControlBase field has no matching key in this map, it is silently ignored.

### `protocol.modbus.reads` (read map)

Maps semantic names to Modbus input register addresses. These registers are **read once at startup** to populate the `DERState` that drives the XML settings files sent to the server.

| Key | DERState field | Used in |
|-----|----------------|---------|
| `inverter_status` | `inverterStatus` | DERStatus.xml |
| `gen_connect_status` | `genConnectStatus` | DERStatus.xml |
| `state_of_charge` | `stateOfCharge` | DERAvailability.xml |
| `available_w` | `statWAvail` | DERAvailability.xml |
| `available_var` | `statVarAvail` | DERAvailability.xml |
| `rated_w` | `rtgW` | DERCapability.xml |
| `rated_va` | `rtgVA` | DERCapability.xml |
| `rated_ah` | `rtgAh` | DERCapability.xml |
| `max_w` | `rtgMaxW` | DERCapability.xml |
| `max_a` | `rtgMaxA` | DERCapability.xml |

If a register cannot be read (device offline, address out of range), the corresponding `DERState` field falls back to a default value (typically `0` or `None`). The gateway does not abort startup on individual read failures.

---

## `logging`

```yaml
logging:
  level: INFO
  format: text
  file: null
```

| Field | Values | Default | Description |
|-------|--------|---------|-------------|
| `level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` | Python log level |
| `format` | `text`, `json` | `text` | `text` for human-readable output; `json` for structured log ingestion (one JSON object per line) |
| `file` | path or `null` | `null` | If set, also write logs to this file in addition to stderr |

---

## Full Example

```yaml
device:
  sfdi: "320841683177"
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"

server:
  interface: "eth0"
  uri: "https://192.168.1.100/sep2"
  command: "all"

protocol:
  type: modbus
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:
      active_power:    40100
      reactive_power:  40101
      max_power_limit: 40102
      ramp_time:       40103
      connect:         40104
      energize:        40105
    reads:
      inverter_status:     30201
      gen_connect_status:  30202
      state_of_charge:     30200
      available_w:         30203
      available_var:       30204
      rated_w:             30300
      rated_va:            30301
      rated_ah:            30302
      max_w:               30303
      max_a:               30304

logging:
  level: INFO
  format: text
```

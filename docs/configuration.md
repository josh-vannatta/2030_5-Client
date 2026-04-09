# Configuration

All runtime configuration lives in `config/gateway.yaml` by default. An alternate file can be provided with `--config <path>`. Environment variables can override selected identity fields without editing the file. 

### Environment overrides

| Env var        | YAML key      | Purpose                   |
| -------------- | ------------- | ------------------------- |
| `GATEWAY_SFDI` | `device.sfdi` | override SFDI             |
| `GATEWAY_PIN`  | `device.pin`  | inject in-band PIN        |
| `GATEWAY_CERT` | `device.cert` | override certificate path |

These overrides are applied during config load before validation.  

### Configuration structure

The config file is organized into five top-level sections:

* `device`
* `server`
* `protocol`
* `logging`
* `telemetry`

### `device`

The `device` block defines identity and certificate settings.

```yaml id="5gr0cu"
device:
  sfdi: "320841683177"
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"
```

Key points:

* `sfdi` is derived from the device certificate
* `cert` must point to the device PEM
* `ca_dir` must contain the trusted CA certificate(s)
* `pin` is only needed if in-band registration is required by the server 

### `server`

The `server` block defines outbound IEEE 2030.5 connection settings.

```yaml id="7ocbck"
server:
  interface: "eth0"
  uri: "https://192.168.1.100/sep2"
  command: "all"
  poll_rate: 300
```

Operational meaning:

* `interface` is passed through to the C client
* `uri` is the 2030.5 server base URI
* `command` selects the C-client operation mode, with `all` as the normal setting
* `poll_rate` sets the `DERControlList` poll interval in seconds (default `300`); passed to `client_test` as `poll <n>`. Controls how quickly the gateway detects new or changed DER controls. Note: `FunctionSetAssignmentsList`, `DERProgramList`, and `Time` use the server's own `pollRate` field and are unaffected by this setting.

### `protocol`

The `protocol` block defines southbound communication and the register map.

```yaml id="4qfmkj"
protocol:
  type: modbus
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:
      active_power: 40100
      reactive_power: 40101
      max_power_limit: 40102
      ramp_time: 40103
      connect: 40104
      energize: 40105
    reads:
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
```

Current operational status:

* `modbus` is implemented
* `dnp3` is planned but currently raises `NotImplementedError`  

#### `registers` write map

These are the holding registers written when a DER event is applied and zeroed during relinquish. If a DER control field has no mapped register, it is ignored. 

#### `reads` startup read map

These are the addresses read once at startup to populate `DERState`, which then drives XML generation. Read failures fall back to default values and do not abort startup.  

### `logging`

```yaml id="6exsp9"
logging:
  level: INFO
  format: text
  file: null
```

Supported behavior:

* `level` controls Python logging verbosity
* `format` can be `text` or `json`
* `file` optionally duplicates output to a file path

### `telemetry`

Controls OpenTelemetry export. All three signal types — traces, metrics, and structured logs — share a single endpoint configuration. The `telemetry` section is optional; when absent the gateway runs with zero OTel overhead.

```yaml
telemetry:
  enabled: false
  # endpoint: http://otel-lgtm:4318
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | Activate OTel export. Also auto-enabled by `OTEL_EXPORTER_OTLP_ENDPOINT` in the environment. |
| `endpoint` | string | — | Base OTLP/HTTP endpoint. Signals go to `{endpoint}/v1/traces`, `/v1/metrics`, `/v1/logs`. Omit to rely on the env var or the SDK default (`http://localhost:4318`). |

Telemetry is activated when **either** `enabled: true` is set in config **or** `OTEL_EXPORTER_OTLP_ENDPOINT` is present in the environment. When both are absent the gateway starts with no OTel code loaded and no network connections attempted.

#### Environment variable reference

All standard OpenTelemetry SDK env vars are honoured automatically. The gateway-specific ones (`GATEWAY_*`) are separate.

| Env var | Purpose |
| --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base OTLP/HTTP endpoint; also auto-enables telemetry |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Per-signal override for traces |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | Per-signal override for metrics |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | Per-signal override for logs |
| `OTEL_SERVICE_NAME` | Service name shown in Grafana (default: `ieee2030-gateway`) |
| `OTEL_RESOURCE_ATTRIBUTES` | Additional resource tags, comma-separated `key=value` pairs |

#### Exported signals

**Traces**

| Span | Source | Key attributes |
| --- | --- | --- |
| `gateway.run` | `__main__` | `server_uri`, `protocol`, `sfdi` |
| `epri_client.session` | `client.py` | `binary`, `pid` |
| `bridge.event` | `bridge.py` | `event_type`, `sfdi` |

**Metrics**

| Metric | Type | Description |
| --- | --- | --- |
| `gateway_client_runs_total` | counter | C binary subprocess starts |
| `gateway_client_events_total` | counter | `EVENT_JSON` lines parsed (tagged `event_type`) |
| `gateway_client_errors_total` | counter | Non-zero subprocess exits |
| `gateway_client_run_duration_ms` | histogram | Full subprocess session duration |
| `gateway_bridge_events_total` | counter | DERControl events applied (tagged `event_type`) |
| `gateway_bridge_errors_total` | counter | Modbus write failures (tagged `register`) |
| `gateway_modbus_reads_total` | counter | `read_register` calls |
| `gateway_modbus_writes_total` | counter | `write_register` calls |
| `gateway_modbus_errors_total` | counter | Modbus exceptions (tagged `operation`) |

**Logs**

All Python `logging` output is forwarded to the OTel log signal via a `LoggingHandler` attached to the root logger at startup. No changes to existing log call sites are required. The `level`, `format`, and `file` settings in the `logging` section continue to control console/file output independently.

#### Required packages

The OTel packages are an optional dependency group and are not installed by default:

```bash
uv sync --group otel
```

The gateway will log a warning and continue normally if telemetry is enabled in config but the packages are not installed. See [development.md](development.md) for a local collector setup guide.

## Full example config

```yaml id="m9glh0"
device:
  sfdi: "320841683177"
  cert: "config/certs/device.pem"
  ca_dir: "config/certs/ca/"
  pin: "111115"

server:
  interface: "eth0"
  uri: "https://192.168.1.100/sep2"
  command: "all"
  poll_rate: 300

protocol:
  type: modbus
  modbus:
    host: "192.168.1.200"
    port: 502
    unit_id: 1
    registers:
      active_power: 40100
      reactive_power: 40101
      max_power_limit: 40102
      ramp_time: 40103
      connect: 40104
      energize: 40105
    reads:
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
  format: text

telemetry:
  enabled: false
  # endpoint: http://otel-lgtm:4318
```

## Documentation
* [readme.md](../README.md) — overview, quickstart, repo map
* [docs/architecture.md](architecture.md) — system boundaries, process model, IPC, data flows
* [docs/configuration.md](configuration.md) — app configuration, environment variables, 
* [docs/sequence.md](sequence.md) — lifecycle, runtime state, configuration, failure behavior
* [docs/development.md](development.md) — setup, testing, certificates, extension workflow
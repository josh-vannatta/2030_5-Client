
## Configuration

All runtime configuration lives in `config/gateway.yaml` by default. An alternate file can be provided with `--config <path>`. Environment variables can override selected identity fields without editing the file. 

### Environment overrides

| Env var        | YAML key      | Purpose                   |
| -------------- | ------------- | ------------------------- |
| `GATEWAY_SFDI` | `device.sfdi` | override SFDI             |
| `GATEWAY_PIN`  | `device.pin`  | inject in-band PIN        |
| `GATEWAY_CERT` | `device.cert` | override certificate path |

These overrides are applied during config load before validation.  

### Configuration structure

The config file is organized into four top-level sections:

* `device`
* `server`
* `protocol`
* `logging` 

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
```

Operational meaning:

* `interface` is passed through to the C client
* `uri` is the 2030.5 server base URI
* `command` selects the C-client operation mode, with `all` as the normal setting 

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
```
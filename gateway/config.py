"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class RegisterMap:
    """Modbus holding-register addresses for DER control outputs (writes)."""

    active_power: int = 40100    # opModFixedW / opModTargetW  (signed %)
    reactive_power: int = 40101  # opModFixedVar / opModTargetVar
    max_power_limit: int = 40102  # opModMaxLimW  (unsigned %)
    ramp_time: int = 40103       # rampTms  (1/100 s)
    connect: int = 40104         # opModConnect  (0=disconnect, 1=connect)
    energize: int = 40105        # opModEnergize (0=de-energize, 1=energize)


@dataclass
class ReadMap:
    """Modbus input-register addresses for DER telemetry (reads).

    All fields are optional (None = not wired / use default). Registers are
    read at startup to populate DERCapability/Settings/Status/Availability XML
    before the 2030.5 client connects to the server.
    """

    # ── Live status & availability ─────────────────────────────────────────
    inverter_status: int | None = None     # inverter status code (se DERStatus)
    gen_connect_status: int | None = None  # generator connect status (0/1)
    state_of_charge: int | None = None     # battery SOC % (0–100; 0 if no storage)
    available_w: int | None = None         # available active power (W)
    available_var: int | None = None       # available reactive power (VAR)

    # ── Static capability (read once at startup) ───────────────────────────
    rated_w: int | None = None             # rated active power (W)
    rated_va: int | None = None            # rated apparent power (VA)
    rated_ah: int | None = None            # rated capacity (Ah; 0 if no storage)

    # ── Operator-configured limits ─────────────────────────────────────────
    max_w: int | None = None               # max active power output (W)
    max_a: int | None = None               # max current (A)

    # ── Metering ──────────────────────────────────────────────────────────
    active_power_output: int | None = None    # current active power output (W)
    reactive_power_output: int | None = None  # current reactive power output (VAR)
    energy_delivered_wh: int | None = None    # cumulative energy delivered (Wh)


@dataclass
class ModbusConfig:
    host: str
    port: int = 502
    unit_id: int = 1
    timeout: float = 5.0
    registers: RegisterMap = field(default_factory=RegisterMap)
    reads: ReadMap = field(default_factory=ReadMap)


@dataclass
class Dnp3Config:
    host: str
    port: int = 20000
    master_address: int = 1
    outstation_address: int = 10


@dataclass
class LogConfig:
    level: str = "INFO"
    format: Literal["json", "text"] = "text"
    file: str | None = None


@dataclass
class TelemetryConfig:
    """OpenTelemetry export settings.

    Telemetry is activated when ``enabled`` is True *or* when
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` is present in the environment.
    When both are unset the gateway runs with zero OTel overhead.
    """

    enabled: bool = False
    # Base OTLP/HTTP endpoint. Signals are posted to {endpoint}/v1/{signal}.
    # Omit to rely on OTEL_EXPORTER_OTLP_ENDPOINT (or the SDK default
    # http://localhost:4318).  Per-signal env vars always take precedence:
    #   OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
    #   OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
    #   OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
    endpoint: str | None = None


@dataclass
class Config:
    # Network interface the C client listens on (e.g. eth0)
    interface: str
    # 2030.5 server base URI
    server_uri: str
    # Path to device certificate (PEM)
    cert: str
    # Directory containing CA certificates
    ca_dir: str
    # Short-Form Device Identifier (numeric string)
    sfdi: str
    # Startup command passed to client_test binary
    command: str = "all"
    # DERControlList poll interval in seconds (passed as `poll <n>` to client_test)
    # Defaults to 300 s (the client_test hardcoded default in core/schedule.c)
    poll_rate: int = 300
    # PIN for in-band registration (optional)
    pin: str | None = None
    # Field protocol type
    protocol: Literal["modbus", "dnp3"] = "modbus"
    modbus: ModbusConfig | None = None
    dnp3: Dnp3Config | None = None
    log: LogConfig = field(default_factory=LogConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)

    def validate(self) -> None:
        """Raise ValueError for any missing or invalid fields."""
        errors: list[str] = []

        if not self.interface:
            errors.append("interface is required")
        if not self.server_uri:
            errors.append("server_uri is required")
        if not self.sfdi:
            errors.append("sfdi is required")

        cert_path = Path(self.cert)
        if not cert_path.exists():
            errors.append(f"cert not found: {self.cert}")

        ca_path = Path(self.ca_dir)
        if not ca_path.is_dir():
            errors.append(f"ca_dir not found or not a directory: {self.ca_dir}")

        if self.protocol == "modbus" and self.modbus is None:
            errors.append("protocol is modbus but modbus config is missing")
        if self.protocol == "dnp3" and self.dnp3 is None:
            errors.append("protocol is dnp3 but dnp3 config is missing")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))


def load(path: str | Path) -> Config:
    """Load and validate gateway configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    _apply_env_overrides(raw)

    try:
        cfg = _build(raw)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid config structure: {exc}") from exc

    cfg.validate()
    return cfg


def _apply_env_overrides(raw: dict) -> None:
    """Allow secrets to be injected via environment variables."""
    overrides = {
        "GATEWAY_SFDI": ("device", "sfdi"),
        "GATEWAY_PIN": ("device", "pin"),
        "GATEWAY_CERT": ("device", "cert"),
    }
    for env_var, (section, key) in overrides.items():
        value = os.environ.get(env_var)
        if value is not None:
            raw.setdefault(section, {})[key] = value


def _build(raw: dict) -> Config:
    device = raw.get("device", {})
    server = raw.get("server", {})
    proto = raw.get("protocol", {})
    log_raw = raw.get("logging", {})
    telemetry_raw = raw.get("telemetry", {})

    modbus_cfg = None
    dnp3_cfg = None
    proto_type = proto.get("type", "modbus")

    if proto_type == "modbus" and "modbus" in proto:
        mb = proto["modbus"]
        reg_raw = mb.get("registers", {})
        reads_raw = mb.get("reads", {})
        modbus_cfg = ModbusConfig(
            host=mb["host"],
            port=mb.get("port", 502),
            unit_id=mb.get("unit_id", 1),
            timeout=mb.get("timeout", 5.0),
            registers=RegisterMap(**reg_raw) if reg_raw else RegisterMap(),
            reads=ReadMap(**reads_raw) if reads_raw else ReadMap(),
        )
    elif proto_type == "dnp3" and "dnp3" in proto:
        d = proto["dnp3"]
        dnp3_cfg = Dnp3Config(
            host=d["host"],
            port=d.get("port", 20000),
            master_address=d.get("master_address", 1),
            outstation_address=d.get("outstation_address", 10),
        )

    return Config(
        interface=server.get("interface", ""),
        server_uri=server.get("uri", ""),
        cert=device.get("cert", ""),
        ca_dir=device.get("ca_dir", ""),
        sfdi=str(device.get("sfdi", "")),
        command=server.get("command", "all"),
        poll_rate=int(server.get("poll_rate", 300)),
        pin=str(device["pin"]) if device.get("pin") else None,
        protocol=proto_type,
        modbus=modbus_cfg,
        dnp3=dnp3_cfg,
        log=LogConfig(
            level=log_raw.get("level", "INFO"),
            format=log_raw.get("format", "text"),
            file=log_raw.get("file"),
        ),
        telemetry=TelemetryConfig(
            enabled=bool(telemetry_raw.get("enabled", False)),
            endpoint=telemetry_raw.get("endpoint") or None,
        ),
    )

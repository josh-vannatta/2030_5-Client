"""OpenTelemetry integration — traces, metrics, and log bridge.

All public functions degrade gracefully to no-ops when either:
  - the opentelemetry packages are not installed, or
  - configure() has not been called.

Activation
----------
Call configure() once at startup (after logging is set up). The gateway
activates telemetry when config.telemetry.enabled is True or when
OTEL_EXPORTER_OTLP_ENDPOINT is set in the environment.

Endpoint resolution (checked in order for each signal):
  1. OTEL_EXPORTER_OTLP_{SIGNAL}_ENDPOINT  (e.g. OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
  2. ``endpoint`` argument passed to configure()
  3. OTEL_EXPORTER_OTLP_ENDPOINT environment variable
  4. http://localhost:4318  (OpenTelemetry default)

Standard env vars honoured automatically by the SDK:
  OTEL_SERVICE_NAME          — overrides the service_name argument
  OTEL_RESOURCE_ATTRIBUTES   — merged into the Resource (key=value,key=value)
"""

from __future__ import annotations

import logging
import os
import socket
from contextlib import contextmanager
from typing import Any, Generator

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import block — all OTel symbols live here
# ---------------------------------------------------------------------------

try:
    from opentelemetry import metrics as _metrics_api
    from opentelemetry import trace as _trace_api
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Module-level state — populated by configure(), None until then
# ---------------------------------------------------------------------------

_tracer: Any = None
_tracer_provider: Any = None
_meter_provider: Any = None
_logger_provider: Any = None

_counters: dict[str, Any] = {}
_histograms: dict[str, Any] = {}

# Instrument names registered at configure() time.
# Counter names follow Prometheus convention (snake_case + _total suffix).
_COUNTER_NAMES: list[str] = [
    "gateway_client_runs_total",        # C binary subprocess starts
    "gateway_client_events_total",      # EVENT_JSON lines parsed
    "gateway_client_errors_total",      # non-zero subprocess exit
    "gateway_bridge_events_total",      # DERControl events applied
    "gateway_bridge_errors_total",      # Modbus write failures in bridge
    "gateway_modbus_reads_total",       # Modbus read_register calls
    "gateway_modbus_writes_total",      # Modbus write_register calls
    "gateway_modbus_errors_total",      # Modbus exceptions
]

_HISTOGRAM_NAMES: list[str] = [
    "gateway_client_run_duration_ms",   # full subprocess session duration
]


# ---------------------------------------------------------------------------
# configure()
# ---------------------------------------------------------------------------

def configure(
    service_name: str,
    endpoint: str | None = None,
    resource_attributes: dict[str, str] | None = None,
) -> None:
    """Set up OTel providers and attach the Python logging bridge.

    Safe to call when OTel packages are absent — logs a warning and returns
    without raising so the gateway continues unaffected.

    Parameters
    ----------
    service_name:
        Value for the ``service.name`` resource attribute. Overridden by
        ``OTEL_SERVICE_NAME`` if that env var is set.
    endpoint:
        Base OTLP/HTTP collector endpoint (e.g. ``http://otel-lgtm:4318``).
        Signals are sent to ``{endpoint}/v1/{signal}`` unless a signal-
        specific env var is set. Falls back to ``OTEL_EXPORTER_OTLP_ENDPOINT``
        then ``http://localhost:4318``.
    resource_attributes:
        Extra key/value pairs merged into the OTel Resource (e.g.
        ``{"device.sfdi": "123456"}``). ``OTEL_RESOURCE_ATTRIBUTES`` from
        the environment is also merged automatically by ``Resource.create()``.
    """
    if not _OTEL_AVAILABLE:
        _log.warning(
            "opentelemetry packages are not installed; telemetry disabled. "
            "Install with: uv sync --group otel"
        )
        return

    global _tracer, _tracer_provider, _meter_provider, _logger_provider

    attrs: dict[str, str] = {
        "service.name": service_name,
        "service.instance.id": socket.gethostname(),
        **(resource_attributes or {}),
    }
    resource = Resource.create(attrs)

    base = (
        endpoint
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    ).rstrip("/")

    def _signal_endpoint(signal: str) -> str:
        specific = os.environ.get(
            f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT"
        )
        return specific if specific else f"{base}/v1/{signal}"

    # -- Traces ---------------------------------------------------------------
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=_signal_endpoint("traces")))
    )
    _trace_api.set_tracer_provider(_tracer_provider)
    _tracer = _trace_api.get_tracer("ieee2030.gateway")

    # -- Metrics --------------------------------------------------------------
    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=_signal_endpoint("metrics"))
            )
        ],
    )
    _metrics_api.set_meter_provider(_meter_provider)
    meter = _metrics_api.get_meter("ieee2030.gateway")

    for name in _COUNTER_NAMES:
        _counters[name] = meter.create_counter(name)
    for name in _HISTOGRAM_NAMES:
        _histograms[name] = meter.create_histogram(name)

    # -- Logs (Python logging bridge) -----------------------------------------
    _logger_provider = LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=_signal_endpoint("logs")))
    )
    set_logger_provider(_logger_provider)
    # Attach to the root logger so every existing logger.* call is forwarded
    # to OTel without any changes to the calling modules.
    logging.getLogger().addHandler(LoggingHandler(logger_provider=_logger_provider))

    _log.info(
        "OpenTelemetry enabled (service=%s, endpoint=%s)",
        service_name,
        base,
    )


# ---------------------------------------------------------------------------
# Public API — all functions are no-op safe
# ---------------------------------------------------------------------------

@contextmanager
def span(name: str, **attributes: Any) -> Generator[None, None, None]:
    """Wrap the enclosed block in an OTel span.

    No-op (zero overhead beyond a None check) when telemetry is not
    configured.  Exceptions that propagate through the span are automatically
    recorded and the span status is set to ERROR by the OTel SDK.

    Usage::

        with telemetry.span("bridge.event", event_type="start", sfdi="123"):
            ...
    """
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name, attributes=attributes):
        yield


def count(name: str, value: int = 1, **attributes: Any) -> None:
    """Increment a named counter by *value*.

    No-op when telemetry is not configured or *name* was not pre-registered.
    """
    counter = _counters.get(name)
    if counter is not None:
        counter.add(value, dict(attributes))


def record(name: str, value: float, **attributes: Any) -> None:
    """Record a histogram observation.

    No-op when telemetry is not configured or *name* was not pre-registered.
    """
    histogram = _histograms.get(name)
    if histogram is not None:
        histogram.record(value, dict(attributes))


def shutdown() -> None:
    """Flush pending telemetry and shut down all providers.

    Safe to call when telemetry was never configured (all providers are None).
    Should be called in a ``finally`` block at the top of ``main()`` to
    ensure buffered spans and metrics are exported before the process exits.
    """
    if _logger_provider is not None:
        _logger_provider.shutdown()
    if _meter_provider is not None:
        _meter_provider.shutdown()
    if _tracer_provider is not None:
        _tracer_provider.shutdown()

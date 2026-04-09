"""Modbus TCP adapter using pymodbus.

Wraps pymodbus.client.ModbusTcpClient behind the FieldProtocol interface.
All register addresses are Modbus data-model addresses (0-based).
"""

from __future__ import annotations

import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from . import FieldProtocol
from .. import telemetry
from ..config import ModbusConfig

logger = logging.getLogger(__name__)


class ModbusAdapter(FieldProtocol):
    def __init__(self, cfg: ModbusConfig) -> None:
        self.cfg = cfg
        self._client: ModbusTcpClient | None = None

    def connect(self) -> None:
        self._client = ModbusTcpClient(
            host=self.cfg.host,
            port=self.cfg.port,
            timeout=self.cfg.timeout,
        )
        if not self._client.connect():
            raise ConnectionError(
                f"Modbus TCP connection failed: {self.cfg.host}:{self.cfg.port}"
            )
        logger.info("Modbus connected: %s:%d unit=%d", self.cfg.host, self.cfg.port, self.cfg.unit_id)

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Modbus disconnected")

    def write_register(self, address: int, value: int) -> None:
        self._require_connected()
        logger.debug("Modbus write reg=%d value=%d", address, value)
        result = self._client.write_register(  # type: ignore[union-attr]
            address=address,
            value=value,
            slave=self.cfg.unit_id,
        )
        if result.isError():
            telemetry.count("gateway_modbus_errors_total", operation="write")
            raise ModbusException(f"Write failed at register {address}: {result}")
        telemetry.count("gateway_modbus_writes_total")

    def read_register(self, address: int) -> int:
        self._require_connected()
        result = self._client.read_holding_registers(  # type: ignore[union-attr]
            address=address,
            count=1,
            slave=self.cfg.unit_id,
        )
        if result.isError():
            telemetry.count("gateway_modbus_errors_total", operation="read")
            raise ModbusException(f"Read failed at register {address}: {result}")
        value: int = result.registers[0]
        logger.debug("Modbus read  reg=%d value=%d", address, value)
        telemetry.count("gateway_modbus_reads_total")
        return value

    def _require_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("ModbusAdapter is not connected. Call connect() first.")

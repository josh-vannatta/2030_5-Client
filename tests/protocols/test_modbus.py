"""Tests for gateway/protocols/modbus.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gateway.config import ModbusConfig, RegisterMap
from gateway.protocols.modbus import ModbusAdapter


@pytest.fixture()
def cfg() -> ModbusConfig:
    return ModbusConfig(host="127.0.0.1", port=502, unit_id=1, registers=RegisterMap())


@pytest.fixture()
def adapter(cfg) -> ModbusAdapter:
    return ModbusAdapter(cfg)


def test_connect_success(adapter):
    with patch("gateway.protocols.modbus.ModbusTcpClient") as MockClient:
        MockClient.return_value.connect.return_value = True
        adapter.connect()
        assert adapter._client is not None


def test_connect_failure_raises(adapter):
    with patch("gateway.protocols.modbus.ModbusTcpClient") as MockClient:
        MockClient.return_value.connect.return_value = False
        with pytest.raises(ConnectionError, match="Modbus TCP connection failed"):
            adapter.connect()


def test_write_register_calls_client(adapter):
    mock_client = MagicMock()
    mock_client.write_register.return_value = MagicMock(isError=lambda: False)
    adapter._client = mock_client

    adapter.write_register(40100, 75)
    mock_client.write_register.assert_called_once_with(
        address=40100, value=75, slave=1
    )


def test_write_register_raises_on_error(adapter):
    from pymodbus.exceptions import ModbusException

    mock_client = MagicMock()
    mock_client.write_register.return_value = MagicMock(isError=lambda: True)
    adapter._client = mock_client

    with pytest.raises(ModbusException):
        adapter.write_register(40100, 75)


def test_read_register_returns_value(adapter):
    mock_client = MagicMock()
    mock_result = MagicMock(isError=lambda: False)
    mock_result.registers = [42]
    mock_client.read_holding_registers.return_value = mock_result
    adapter._client = mock_client

    value = adapter.read_register(40100)
    assert value == 42


def test_write_register_without_connect_raises(adapter):
    with pytest.raises(RuntimeError, match="not connected"):
        adapter.write_register(40100, 0)


def test_disconnect_clears_client(adapter):
    mock_client = MagicMock()
    adapter._client = mock_client
    adapter.disconnect()
    assert adapter._client is None
    mock_client.close.assert_called_once()

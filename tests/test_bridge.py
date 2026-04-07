"""Tests for gateway/bridge.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gateway.bridge import DERBridge
from gateway.config import RegisterMap
from gateway.protocols import FieldProtocol


@pytest.fixture()
def mock_protocol() -> MagicMock:
    proto = MagicMock(spec=FieldProtocol)
    return proto


@pytest.fixture()
def registers() -> RegisterMap:
    return RegisterMap()


@pytest.fixture()
def bridge(mock_protocol, registers) -> DERBridge:
    return DERBridge(protocol=mock_protocol, registers=registers)


# --- start events ---

def test_start_event_writes_active_power(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModFixedW": -50}})
    mock_protocol.write_register.assert_called_with(registers.active_power, -50)


def test_start_event_writes_max_power_limit(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModMaxLimW": 80}})
    mock_protocol.write_register.assert_called_with(registers.max_power_limit, 80)


def test_start_event_writes_ramp_time(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"rampTms": 200}})
    mock_protocol.write_register.assert_called_with(registers.ramp_time, 200)


def test_start_event_connect_true(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModConnect": True}})
    mock_protocol.write_register.assert_called_with(registers.connect, 1)


def test_start_event_connect_false(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModConnect": False}})
    mock_protocol.write_register.assert_called_with(registers.connect, 0)


def test_start_event_energize(bridge, mock_protocol, registers):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModEnergize": True}})
    mock_protocol.write_register.assert_called_with(registers.energize, 1)


def test_start_event_multiple_fields(bridge, mock_protocol, registers):
    bridge.apply({
        "type": "start",
        "sfdi": 111115,
        "control": {"opModFixedW": 100, "rampTms": 50, "opModConnect": True},
    })
    calls = {call.args[0]: call.args[1] for call in mock_protocol.write_register.call_args_list}
    assert calls[registers.active_power] == 100
    assert calls[registers.ramp_time] == 50
    assert calls[registers.connect] == 1


def test_start_event_empty_control_no_writes(bridge, mock_protocol):
    bridge.apply({"type": "start", "sfdi": 111115, "control": {}})
    mock_protocol.write_register.assert_not_called()


# --- end events ---

def test_end_event_no_register_writes(bridge, mock_protocol):
    bridge.apply({"type": "end", "sfdi": 111115, "description": "test"})
    mock_protocol.write_register.assert_not_called()


# --- edge cases ---

def test_unknown_event_type_ignored(bridge, mock_protocol):
    bridge.apply({"type": "unknown"})
    mock_protocol.write_register.assert_not_called()


def test_write_failure_raises(bridge, mock_protocol, registers):
    mock_protocol.write_register.side_effect = ConnectionError("device offline")
    with pytest.raises(ConnectionError, match="device offline"):
        bridge.apply({"type": "start", "sfdi": 111115, "control": {"opModFixedW": 50}})

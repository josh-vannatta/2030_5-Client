"""Tests for gateway/device.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gateway.config import ReadMap
from gateway.device import read_device_state
from gateway.protocols import FieldProtocol
from gateway.settings import DERState


@pytest.fixture()
def mock_protocol() -> MagicMock:
    return MagicMock(spec=FieldProtocol)


@pytest.fixture()
def full_read_map() -> ReadMap:
    return ReadMap(
        inverter_status=30201,
        gen_connect_status=30202,
        state_of_charge=30200,
        available_w=30203,
        available_var=30204,
        rated_w=30300,
        rated_va=30301,
        rated_ah=30302,
        max_w=30303,
        max_a=30304,
    )


# --- No read map ---

def test_no_read_map_returns_defaults(mock_protocol):
    state = read_device_state(mock_protocol, reads=None)
    assert isinstance(state, DERState)
    mock_protocol.read_register.assert_not_called()


def test_no_read_map_uses_der_state_defaults(mock_protocol):
    defaults = DERState()
    state = read_device_state(mock_protocol, reads=None)
    assert state.rtg_w == defaults.rtg_w
    assert state.inverter_status == defaults.inverter_status


# --- Full read map ---

def test_reads_inverter_status(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30201: 4}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.inverter_status == 4


def test_reads_state_of_charge(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30200: 85}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.state_of_charge == 85


def test_reads_available_w(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30203: 1500}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.stat_w_avail == 1500


def test_reads_available_var(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30204: 500}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.stat_var_avail == 500


def test_reads_rated_w(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30300: 5000}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.rtg_w == 5000


def test_reads_max_w(mock_protocol, full_read_map):
    mock_protocol.read_register.side_effect = lambda addr: {30303: 4500}.get(addr, 0)
    state = read_device_state(mock_protocol, full_read_map)
    assert state.set_max_w == 4500


# --- Partial read map (some registers None) ---

def test_partial_read_map_skips_none_registers(mock_protocol):
    reads = ReadMap(inverter_status=30201)  # all others are None
    mock_protocol.read_register.return_value = 7
    state = read_device_state(mock_protocol, reads)
    assert state.inverter_status == 7
    # Only one register should have been read
    mock_protocol.read_register.assert_called_once_with(30201)


def test_partial_read_map_keeps_defaults_for_none(mock_protocol):
    reads = ReadMap()  # all None
    state = read_device_state(mock_protocol, reads)
    mock_protocol.read_register.assert_not_called()
    assert state == DERState()


# --- Error handling ---

def test_failed_read_uses_default_and_continues(mock_protocol, full_read_map):
    defaults = DERState()
    mock_protocol.read_register.side_effect = ConnectionError("device offline")
    # Should not raise — returns defaults
    state = read_device_state(mock_protocol, full_read_map)
    assert state.inverter_status == defaults.inverter_status
    assert state.rtg_w == defaults.rtg_w


def test_partial_failure_keeps_successful_reads(mock_protocol, full_read_map):
    def side_effect(addr):
        if addr == 30201:
            return 4  # inverter_status OK
        raise ConnectionError("timeout")

    mock_protocol.read_register.side_effect = side_effect
    state = read_device_state(mock_protocol, full_read_map)
    assert state.inverter_status == 4
    assert state.rtg_w == DERState().rtg_w  # default preserved on failure

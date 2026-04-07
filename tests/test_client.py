"""Tests for gateway/client.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from gateway.client import EpriClient, EpriClientError, EVENT_PREFIX


@pytest.fixture()
def client(gateway_config, tmp_path):
    """EpriClient pointed at a fake binary path."""
    fake_binary = tmp_path / "client_test"
    fake_binary.touch(mode=0o755)
    return EpriClient(gateway_config, binary=fake_binary)


def _make_stdout(*lines: str) -> MagicMock:
    """Build a mock stdout that yields the given lines."""
    mock = MagicMock()
    mock.__iter__ = MagicMock(return_value=iter(lines))
    return mock


def test_build_args_includes_interface(client, gateway_config):
    args = client._build_args()
    assert args[1] == gateway_config.interface


def test_build_args_includes_server_uri(client, gateway_config):
    args = client._build_args()
    assert gateway_config.server_uri in args


def test_build_args_includes_pin(client, gateway_config):
    gateway_config.pin = "12345"
    args = client._build_args()
    assert "pin" in args
    assert "12345" in args


def test_build_args_no_pin_when_not_set(client, gateway_config):
    gateway_config.pin = None
    args = client._build_args()
    assert "pin" not in args


def test_events_yields_parsed_json(client):
    event = {"type": "start", "sfdi": 111115, "control": {"opModFixedW": -50}}
    line = f"{EVENT_PREFIX}{json.dumps(event)}\n"
    debug_line = "Event Start \"test\" -- Mon Jan  1 00:00:00 2024\n"

    proc = MagicMock()
    proc.stdout = _make_stdout(line, debug_line)
    proc.wait.return_value = 0
    client._proc = proc

    events = list(client.events())
    assert len(events) == 1
    assert events[0]["type"] == "start"
    assert events[0]["control"]["opModFixedW"] == -50


def test_events_skips_non_json_lines(client):
    proc = MagicMock()
    proc.stdout = _make_stdout(
        "some debug output\n",
        "another debug line\n",
    )
    proc.wait.return_value = 0
    client._proc = proc

    events = list(client.events())
    assert events == []


def test_events_raises_on_nonzero_exit(client):
    proc = MagicMock()
    proc.stdout = _make_stdout()
    proc.wait.return_value = 1
    client._proc = proc

    with pytest.raises(EpriClientError, match="exited with code 1"):
        list(client.events())


def test_events_raises_if_not_started(client):
    with pytest.raises(EpriClientError, match="not started"):
        list(client.events())


def test_start_raises_if_binary_missing(gateway_config, tmp_path):
    client = EpriClient(gateway_config, binary=tmp_path / "nonexistent")
    with pytest.raises(EpriClientError, match="binary not found"):
        client.start()


def test_malformed_json_line_is_skipped(client):
    proc = MagicMock()
    proc.stdout = _make_stdout(f"{EVENT_PREFIX}{{not valid json}}\n")
    proc.wait.return_value = 0
    client._proc = proc

    events = list(client.events())
    assert events == []

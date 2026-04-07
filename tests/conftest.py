"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.config import Config, ModbusConfig, RegisterMap, LogConfig


@pytest.fixture()
def certs_dir(tmp_path: Path) -> Path:
    """A temporary certs directory with a placeholder device cert."""
    ca = tmp_path / "ca"
    ca.mkdir()
    cert = tmp_path / "device.pem"
    cert.write_text("# placeholder cert\n")
    return tmp_path


@pytest.fixture()
def modbus_config() -> ModbusConfig:
    return ModbusConfig(
        host="127.0.0.1",
        port=502,
        unit_id=1,
        registers=RegisterMap(),
    )


@pytest.fixture()
def gateway_config(certs_dir: Path, modbus_config: ModbusConfig) -> Config:
    return Config(
        interface="eth0",
        server_uri="https://192.168.1.1/sep2",
        cert=str(certs_dir / "device.pem"),
        ca_dir=str(certs_dir / "ca"),
        sfdi="111115",
        command="all",
        protocol="modbus",
        modbus=modbus_config,
        log=LogConfig(),
    )

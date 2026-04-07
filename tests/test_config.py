"""Tests for gateway/config.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from gateway.config import load, Config, ModbusConfig, RegisterMap


def _write_yaml(path: Path, data: dict) -> Path:
    cfg_file = path / "gateway.yaml"
    cfg_file.write_text(yaml.dump(data))
    return cfg_file


@pytest.fixture()
def valid_yaml_data(certs_dir):
    return {
        "device": {
            "sfdi": "111115",
            "cert": str(certs_dir / "device.pem"),
            "ca_dir": str(certs_dir / "ca"),
            "pin": "111115",
        },
        "server": {
            "interface": "eth0",
            "uri": "https://192.168.1.1/sep2",
            "command": "all",
        },
        "protocol": {
            "type": "modbus",
            "modbus": {"host": "192.168.1.2", "port": 502, "unit_id": 1},
        },
        "logging": {"level": "INFO", "format": "text"},
    }


def test_load_valid_config(tmp_path, valid_yaml_data):
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    cfg = load(cfg_file)
    assert cfg.sfdi == "111115"
    assert cfg.interface == "eth0"
    assert cfg.protocol == "modbus"
    assert cfg.modbus is not None
    assert cfg.modbus.host == "192.168.1.2"


def test_load_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nonexistent.yaml")


def test_missing_cert_raises(tmp_path, valid_yaml_data):
    valid_yaml_data["device"]["cert"] = "/nonexistent/device.pem"
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    with pytest.raises(ValueError, match="cert not found"):
        load(cfg_file)


def test_missing_ca_dir_raises(tmp_path, valid_yaml_data):
    valid_yaml_data["device"]["ca_dir"] = "/nonexistent/ca"
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    with pytest.raises(ValueError, match="ca_dir not found"):
        load(cfg_file)


def test_modbus_config_missing_when_protocol_modbus(tmp_path, valid_yaml_data):
    del valid_yaml_data["protocol"]["modbus"]
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    with pytest.raises(ValueError, match="modbus config is missing"):
        load(cfg_file)


def test_pin_is_optional(tmp_path, valid_yaml_data):
    del valid_yaml_data["device"]["pin"]
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    cfg = load(cfg_file)
    assert cfg.pin is None


def test_env_override_sfdi(tmp_path, valid_yaml_data, monkeypatch):
    monkeypatch.setenv("GATEWAY_SFDI", "999999")
    cfg_file = _write_yaml(tmp_path, valid_yaml_data)
    cfg = load(cfg_file)
    assert cfg.sfdi == "999999"


def test_default_register_map():
    regs = RegisterMap()
    assert regs.active_power == 40100
    assert regs.connect == 40104

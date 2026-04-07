"""Tests for gateway/settings.py."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from gateway.settings import DERState, write_settings

NS = "urn:ieee:std:2030.5:ns"


def _el(root, tag):
    return root.find(f".//{{{NS}}}{tag}")


def test_write_settings_creates_all_four_files(tmp_path):
    write_settings(DERState(), tmp_path)
    assert (tmp_path / "DERCapability.xml").exists()
    assert (tmp_path / "DERSettings.xml").exists()
    assert (tmp_path / "DERStatus.xml").exists()
    assert (tmp_path / "DERAvailability.xml").exists()


def test_capability_rtg_w(tmp_path):
    state = DERState(rtg_w=5000)
    write_settings(state, tmp_path)
    root = ET.parse(tmp_path / "DERCapability.xml").getroot()
    assert _el(root, "rtgMaxW").find(f"{{{NS}}}value").text == "5000"


def test_settings_max_w(tmp_path):
    state = DERState(set_max_w=3000)
    write_settings(state, tmp_path)
    root = ET.parse(tmp_path / "DERSettings.xml").getroot()
    assert _el(root, "setMaxW").find(f"{{{NS}}}value").text == "3000"


def test_status_inverter_status(tmp_path):
    state = DERState(inverter_status=7)
    write_settings(state, tmp_path)
    root = ET.parse(tmp_path / "DERStatus.xml").getroot()
    assert _el(root, "inverterStatus").find(f"{{{NS}}}value").text == "7"


def test_availability_stat_w_avail(tmp_path):
    state = DERState(stat_w_avail=500)
    write_settings(state, tmp_path)
    root = ET.parse(tmp_path / "DERAvailability.xml").getroot()
    assert _el(root, "statWAvail").find(f"{{{NS}}}value").text == "500"


def test_write_settings_creates_directory(tmp_path):
    target = tmp_path / "new" / "nested" / "dir"
    write_settings(DERState(), target)
    assert (target / "DERCapability.xml").exists()

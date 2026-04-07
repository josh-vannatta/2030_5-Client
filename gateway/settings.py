"""Generate DER settings XML files consumed by the EPRI client binary.

The C binary loads four XML files from the settings/ directory at startup.
This module generates those files from a DERState dataclass so that
field-protocol reads (Modbus/DNP3) can be reflected to the 2030.5 server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DERState:
    """Snapshot of a DER device's current state.

    Units follow IEEE 2030.5 conventions:
      - power values: watts (W)
      - percent values: 0-100
      - voltage: 10ths of a volt (e.g. 1050 = 105.0 V)
    """

    # --- Capability (static hardware ratings) ---
    rtg_w: int = 2000        # rated active power (W)
    rtg_va: int = 2000       # rated apparent power (VA)
    rtg_ah: int = 20         # rated capacity (Ah), 0 if N/A

    # --- Settings (operator-configured limits) ---
    set_max_w: int = 1800    # max active power output (W)
    set_max_a: int = 9       # max current (A)
    set_es_high_volt: int = 1050  # high-voltage setpoint (10ths V)
    set_es_low_volt: int = 950    # low-voltage setpoint (10ths V)

    # --- Status (live device state) ---
    inverter_status: int = 4     # 4 = generating
    state_of_charge: int = 70    # battery SOC %  (0 if no storage)
    gen_connect_status: int = 1  # 1 = connected

    # --- Availability (available power right now) ---
    stat_w_avail: int = 200   # available active power (W)
    stat_var_avail: int = 200  # available reactive power (VAR)


def write_settings(state: DERState, directory: str | Path) -> None:
    """Write all four DER XML settings files to *directory*."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    (directory / "DERCapability.xml").write_text(_capability(state))
    (directory / "DERSettings.xml").write_text(_settings(state))
    (directory / "DERStatus.xml").write_text(_status(state))
    (directory / "DERAvailability.xml").write_text(_availability(state))


# ---------------------------------------------------------------------------
# XML generators
# ---------------------------------------------------------------------------

def _capability(s: DERState) -> str:
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<DERCapability xmlns="urn:ieee:std:2030.5:ns">
  <modesSupported>0</modesSupported>
  <rtgAh>
    <multiplier>0</multiplier>
    <value>{s.rtg_ah}</value>
  </rtgAh>
  <rtgMaxW>
    <multiplier>0</multiplier>
    <value>{s.rtg_w}</value>
  </rtgMaxW>
  <rtgVA>
    <multiplier>0</multiplier>
    <value>{s.rtg_va}</value>
  </rtgVA>
</DERCapability>
"""


def _settings(s: DERState) -> str:
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<DERSettings xmlns="urn:ieee:std:2030.5:ns">
  <setESHighVolt>{s.set_es_high_volt}</setESHighVolt>
  <setESLowVolt>{s.set_es_low_volt}</setESLowVolt>
  <setMaxA>
    <multiplier>0</multiplier>
    <value>{s.set_max_a}</value>
  </setMaxA>
  <setMaxW>
    <multiplier>0</multiplier>
    <value>{s.set_max_w}</value>
  </setMaxW>
</DERSettings>
"""


def _status(s: DERState) -> str:
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<DERStatus xmlns="urn:ieee:std:2030.5:ns">
  <genConnectStatus>
    <dateTime>0</dateTime>
    <value>{s.gen_connect_status}</value>
  </genConnectStatus>
  <inverterStatus>
    <dateTime>0</dateTime>
    <value>{s.inverter_status}</value>
  </inverterStatus>
  <stateOfChargeStatus>
    <dateTime>0</dateTime>
    <value>{s.state_of_charge}</value>
  </stateOfChargeStatus>
</DERStatus>
"""


def _availability(s: DERState) -> str:
    return f"""\
<?xml version="1.0" encoding="utf-8"?>
<DERAvailability xmlns="urn:ieee:std:2030.5:ns">
  <statVarAvail>
    <multiplier>0</multiplier>
    <value>{s.stat_var_avail}</value>
  </statVarAvail>
  <statWAvail>
    <multiplier>0</multiplier>
    <value>{s.stat_w_avail}</value>
  </statWAvail>
</DERAvailability>
"""

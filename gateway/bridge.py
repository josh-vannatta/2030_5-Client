"""DER control bridge — maps 2030.5 DERControl events to field protocol writes.

Receives event dicts from EpriClient.events() and translates the
DERControlBase fields into register writes via a FieldProtocol adapter.

IEEE 2030.5 DERControlBase field semantics (relevant subset):
  opModFixedW    int16  Signed percent of rated capacity  (-100 to 100)
  opModMaxLimW   uint16 Max power limit, percent of rated (0 to 100)
  opModTargetW   int16  Absolute active power target (W), with multiplier
  opModFixedVar  int16  Fixed reactive power, percent of rated
  opModTargetVar int16  Absolute reactive power target (VAR)
  rampTms        uint16 Ramp time in 1/100 seconds
  opModConnect   bool   True = connect, False = disconnect
  opModEnergize  bool   True = energize, False = de-energize
"""

from __future__ import annotations

import logging
from typing import Any

from .config import RegisterMap
from .protocols import FieldProtocol

logger = logging.getLogger(__name__)


class DERBridge:
    """Translates 2030.5 DERControl events to field protocol register writes."""

    def __init__(self, protocol: FieldProtocol, registers: RegisterMap) -> None:
        self.protocol = protocol
        self.registers = registers

    def apply(self, event: dict[str, Any]) -> None:
        """Process one event dict from EpriClient.events()."""
        event_type = event.get("type")
        sfdi = event.get("sfdi")
        description = event.get("description", "")

        if event_type == "start":
            control = event.get("control", {})
            logger.info(
                "EVENT START sfdi=%s desc=%r control=%s", sfdi, description, control
            )
            self._apply_control(control)

        elif event_type == "end":
            logger.info("EVENT END   sfdi=%s desc=%r — relinquishing control", sfdi, description)
            self._relinquish()

        else:
            logger.debug("Unhandled event type %r: %s", event_type, event)

    # ------------------------------------------------------------------
    # Control application
    # ------------------------------------------------------------------

    def _apply_control(self, control: dict[str, Any]) -> None:
        reg = self.registers

        if "opModFixedW" in control:
            self._write(reg.active_power, int(control["opModFixedW"]))

        if "opModTargetW" in control:
            self._write(reg.active_power, int(control["opModTargetW"]))

        if "opModMaxLimW" in control:
            self._write(reg.max_power_limit, int(control["opModMaxLimW"]))

        if "opModFixedVar" in control:
            self._write(reg.reactive_power, int(control["opModFixedVar"]))

        if "opModTargetVar" in control:
            self._write(reg.reactive_power, int(control["opModTargetVar"]))

        if "rampTms" in control:
            self._write(reg.ramp_time, int(control["rampTms"]))

        if "opModConnect" in control:
            self._write(reg.connect, 1 if control["opModConnect"] else 0)

        if "opModEnergize" in control:
            self._write(reg.energize, 1 if control["opModEnergize"] else 0)

    def _relinquish(self) -> None:
        """Return device to local/default control.

        The right behaviour is site-specific. At minimum, clear any active
        setpoints so the device reverts to its own internal defaults.
        Extend this method for your device's relinquish semantics.
        """
        logger.debug("Relinquish: no active setpoints written")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write(self, address: int, value: int) -> None:
        try:
            self.protocol.write_register(address, value)
        except Exception:
            logger.exception("Failed to write register %d = %d", address, value)
            raise


def make_bridge(config) -> DERBridge:
    """Factory: build a DERBridge from a Config object."""
    from .protocols.modbus import ModbusAdapter
    from .protocols.dnp3 import Dnp3Adapter

    if config.protocol == "modbus":
        if config.modbus is None:
            raise ValueError("Modbus config is required when protocol=modbus")
        proto = ModbusAdapter(config.modbus)
        regs = config.modbus.registers
    elif config.protocol == "dnp3":
        if config.dnp3 is None:
            raise ValueError("DNP3 config is required when protocol=dnp3")
        proto = Dnp3Adapter(config.dnp3)
        regs = RegisterMap()  # DNP3 uses point indices, not Modbus addresses
    else:
        raise ValueError(f"Unknown protocol: {config.protocol}")

    return DERBridge(protocol=proto, registers=regs)

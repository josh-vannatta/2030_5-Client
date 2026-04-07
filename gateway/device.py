"""Read live DER device state from the field protocol.

Called at startup (before the C binary launches) so that
DERCapability / DERSettings / DERStatus / DERAvailability XML files
reflect the actual device rather than hard-coded defaults.

Each field in ReadMap maps to one Modbus register. If the address is None
(not wired in config) the corresponding DERState field keeps its default.
A failed read logs a warning and keeps the default — the gateway continues
rather than refusing to start because a single register is unavailable.
"""

from __future__ import annotations

import logging

from .config import ReadMap
from .protocols import FieldProtocol
from .settings import DERState

logger = logging.getLogger(__name__)


def read_device_state(protocol: FieldProtocol, reads: ReadMap | None) -> DERState:
    """Read current device state and return a populated DERState.

    If *reads* is None (e.g. DNP3 not yet implemented, or no reads: block
    in config) returns a DERState with all default values and logs a warning.
    """
    state = DERState()

    if reads is None:
        logger.warning(
            "No read map configured — using default DERState values. "
            "Add a reads: block to the modbus config to populate from device."
        )
        return state

    def _read(address: int | None, name: str, default: int) -> int:
        if address is None:
            return default
        try:
            value = protocol.read_register(address)
            logger.debug("Read %s = %d (reg %d)", name, value, address)
            return value
        except Exception as exc:
            logger.warning(
                "Failed to read %s at register %d: %s — using default %d",
                name, address, exc, default,
            )
            return default

    # ── Status & availability ──────────────────────────────────────────────
    state.inverter_status = _read(
        reads.inverter_status, "inverter_status", state.inverter_status
    )
    state.gen_connect_status = _read(
        reads.gen_connect_status, "gen_connect_status", state.gen_connect_status
    )
    state.state_of_charge = _read(
        reads.state_of_charge, "state_of_charge", state.state_of_charge
    )
    state.stat_w_avail = _read(
        reads.available_w, "available_w", state.stat_w_avail
    )
    state.stat_var_avail = _read(
        reads.available_var, "available_var", state.stat_var_avail
    )

    # ── Static capability ──────────────────────────────────────────────────
    state.rtg_w = _read(reads.rated_w, "rated_w", state.rtg_w)
    state.rtg_va = _read(reads.rated_va, "rated_va", state.rtg_va)
    state.rtg_ah = _read(reads.rated_ah, "rated_ah", state.rtg_ah)

    # ── Operator limits ────────────────────────────────────────────────────
    state.set_max_w = _read(reads.max_w, "max_w", state.set_max_w)
    state.set_max_a = _read(reads.max_a, "max_a", state.set_max_a)

    logger.info(
        "Device state read: inverter_status=%d soc=%d%% avail_w=%dW avail_var=%dVAR "
        "rtg_w=%dW set_max_w=%dW",
        state.inverter_status,
        state.state_of_charge,
        state.stat_w_avail,
        state.stat_var_avail,
        state.rtg_w,
        state.set_max_w,
    )
    return state

"""DNP3 adapter stub.

DNP3 support is not yet implemented. This module exists as a placeholder
so that the protocol selection logic in bridge.py doesn't need to change
when DNP3 is added.

A full implementation would use pydnp3 or a similar library to map
DER control points to DNP3 analog outputs / binary outputs.
"""

from __future__ import annotations

from . import FieldProtocol
from ..config import Dnp3Config


class Dnp3Adapter(FieldProtocol):
    def __init__(self, cfg: Dnp3Config) -> None:
        self.cfg = cfg

    def connect(self) -> None:
        raise NotImplementedError("DNP3 adapter is not yet implemented.")

    def disconnect(self) -> None:
        pass

    def write_register(self, address: int, value: int) -> None:
        raise NotImplementedError("DNP3 adapter is not yet implemented.")

    def read_register(self, address: int) -> int:
        raise NotImplementedError("DNP3 adapter is not yet implemented.")

"""Field protocol adapters.

Each adapter implements the FieldProtocol abstract base so that bridge.py
remains protocol-agnostic. Swap the adapter in config without changing
any bridge logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FieldProtocol(ABC):
    """Abstract interface for a field-side DER protocol driver."""

    @abstractmethod
    def connect(self) -> None:
        """Open the connection to the field device."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""

    @abstractmethod
    def write_register(self, address: int, value: int) -> None:
        """Write a single 16-bit register at *address*."""

    @abstractmethod
    def read_register(self, address: int) -> int:
        """Read and return a single 16-bit register at *address*."""

    def __enter__(self) -> "FieldProtocol":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

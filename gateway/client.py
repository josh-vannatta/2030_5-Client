"""Subprocess wrapper for the EPRI IEEE 2030.5 C binary.

Spawns ``epri_client/build/client_test``, reads its stdout line-by-line,
and yields parsed DER events. Lines not prefixed with EVENT_JSON: are
forwarded to the Python logger as debug output.

Event format emitted by the patched der_client.c:
    EVENT_JSON:{"type":"start","sfdi":...,"mrid":"...","description":"...","control":{...}}
    EVENT_JSON:{"type":"end","sfdi":...,"mrid":"...","description":"..."}
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Generator, Iterator

from .config import Config

logger = logging.getLogger(__name__)

EVENT_PREFIX = "EVENT_JSON:"

# Resolved relative to this file's location at import time
_DEFAULT_BINARY = Path(__file__).parent.parent / "epri_client" / "build" / "client_test"


class EpriClientError(RuntimeError):
    pass


class EpriClient:
    """Manages the lifecycle of the EPRI client_test subprocess."""

    def __init__(self, config: Config, binary: Path | str | None = None) -> None:
        self.config = config
        self.binary = Path(binary) if binary else _DEFAULT_BINARY
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not self.binary.exists():
            raise EpriClientError(
                f"client_test binary not found at {self.binary}. "
                "Run `make` inside epri_client/ first."
            )
        args = self._build_args()
        logger.info("Starting EPRI client: %s", " ".join(str(a) for a in args))
        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=None,   # inherit: C debug output goes to the terminal
            text=True,
            bufsize=1,     # line-buffered
        )

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            logger.info("Stopping EPRI client (pid %d)", self._proc.pid)
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def __enter__(self) -> "EpriClient":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Event stream
    # ------------------------------------------------------------------

    def events(self) -> Iterator[dict]:
        """Yield parsed JSON event dicts from the C binary's stdout.

        Blocks until the process exits or is stopped. Non-event lines are
        forwarded to the logger at DEBUG level.
        """
        if self._proc is None:
            raise EpriClientError("Client not started. Call start() first.")

        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            if line.startswith(EVENT_PREFIX):
                payload = line[len(EVENT_PREFIX):]
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("Malformed event JSON: %s", payload)
            else:
                logger.debug("[epri] %s", line)

        rc = self._proc.wait()
        if rc != 0:
            raise EpriClientError(f"client_test exited with code {rc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_args(self) -> list[str]:
        cfg = self.config
        args: list[str] = [str(self.binary), cfg.interface]
        if cfg.cert:
            args.append(cfg.cert)
        if cfg.ca_dir:
            args.append(cfg.ca_dir)
        args.append(cfg.server_uri)
        args.append(cfg.command)
        if cfg.pin:
            args += ["pin", cfg.pin]
        if cfg.sfdi:
            args += ["sfdi", cfg.sfdi]
        return args

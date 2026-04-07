"""Logging setup for the gateway process."""

import logging
import sys
from typing import Literal


def configure(
    level: str = "INFO",
    fmt: Literal["json", "text"] = "text",
    file: str | None = None,
) -> None:
    """Configure root logger.

    Call once at startup before any other module imports logging.
    """
    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        stream_handler.setFormatter(_JsonFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
    handlers.append(stream_handler)

    if file:
        file_handler = logging.FileHandler(file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        data: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = traceback.format_exception(*record.exc_info)
        return json.dumps(data)

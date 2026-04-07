"""Gateway entry point.

Usage:
    python -m gateway                          # uses config/gateway.yaml
    python -m gateway --config /path/to.yaml
    python -m gateway --config /path/to.yaml --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import log as log_module
from .bridge import make_bridge
from .client import EpriClient
from .config import load
from .settings import DERState, write_settings

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "gateway.yaml"
_SETTINGS_DIR = Path(__file__).parent.parent / "epri_client" / "settings"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IEEE 2030.5 DER gateway")
    parser.add_argument(
        "--config", "-c",
        default=str(_DEFAULT_CONFIG),
        help="Path to gateway.yaml (default: config/gateway.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print resolved settings, then exit",
    )
    args = parser.parse_args(argv)

    # --- Load config ---
    try:
        cfg = load(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # --- Configure logging ---
    log_module.configure(level=cfg.log.level, fmt=cfg.log.format, file=cfg.log.file)

    if args.dry_run:
        logger.info("Config OK — dry run complete")
        print(f"Interface : {cfg.interface}")
        print(f"Server URI: {cfg.server_uri}")
        print(f"SFDI      : {cfg.sfdi}")
        print(f"Protocol  : {cfg.protocol}")
        return 0

    # --- Write DER settings XML from current device state ---
    # TODO: replace DERState() with live reads from the field device
    state = DERState()
    logger.info("Writing DER settings XML to %s", _SETTINGS_DIR)
    write_settings(state, _SETTINGS_DIR)

    # --- Build field protocol bridge ---
    bridge = make_bridge(cfg)

    # --- Run ---
    logger.info("Starting gateway (server=%s, protocol=%s)", cfg.server_uri, cfg.protocol)
    with EpriClient(cfg) as client, bridge.protocol:
        for event in client.events():
            bridge.apply(event)

    return 0


if __name__ == "__main__":
    sys.exit(main())

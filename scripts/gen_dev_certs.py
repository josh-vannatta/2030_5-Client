#!/usr/bin/env python3
"""Generate development certificates for the IEEE 2030.5 gateway.

Creates a self-signed ECDSA P-256 CA and a device certificate, then computes
the SFDI exactly as the EPRI C client does (SHA-256 of raw PEM file bytes).

Usage:
    uv run scripts/gen_dev_certs.py
    uv run scripts/gen_dev_certs.py --out config/certs --config config/gateway.yaml

Outputs:
    config/certs/device.pem      device cert + private key (used by client_test)
    config/certs/ca/ca.pem       CA certificate (trusted by client_test)
    Prints computed SFDI and updates gateway.yaml if --config is given.

Requirements:
    openssl CLI (any modern version with EC support)
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# SFDI computation (mirrors security.c: sfdi_gen + lfdi_hash)
# ---------------------------------------------------------------------------

def check_digit(x: int) -> int:
    """Non-standard check digit: sum of decimal digits, mod 10 complement."""
    total = 0
    while x:
        total += x % 10
        x //= 10
    return (10 - (total % 10)) % 10


def compute_sfdi(pem_path: Path) -> tuple[str, int]:
    """Return (lfdi_hex, sfdi) computed from the raw PEM file bytes.

    Mirrors the C implementation in security.c::lfdi_gen / sfdi_gen:
      1. SHA-256 hash of the raw file bytes
      2. First 20 bytes = LFDI
      3. First 36 bits of LFDI (first 5 bytes >> 4) = base SFDI
      4. Append a check digit
    """
    raw = pem_path.read_bytes()
    digest = hashlib.sha256(raw).digest()
    lfdi = digest[:20]

    sfdi = 0
    for byte in lfdi[:5]:
        sfdi = (sfdi << 8) + byte
    sfdi >>= 4
    sfdi = sfdi * 10 + check_digit(sfdi)

    return lfdi.hex(), sfdi


# ---------------------------------------------------------------------------
# Certificate generation
# ---------------------------------------------------------------------------

def run(cmd: list[str], **kwargs) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"ERROR running: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


def generate_certs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ca_dir = out_dir / "ca"
    ca_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # --- CA key + self-signed cert ---
        ca_key = tmp / "ca.key"
        ca_cert = tmp / "ca.crt"

        run(["openssl", "ecparam", "-genkey", "-name", "prime256v1",
             "-noout", "-out", str(ca_key)])
        run(["openssl", "req", "-new", "-x509",
             "-key", str(ca_key),
             "-out", str(ca_cert),
             "-days", "3650",
             "-subj", "/CN=IEEE 2030.5 Dev CA/O=Development/C=US"])

        # --- Device key + cert signed by CA ---
        dev_key = tmp / "device.key"
        dev_csr = tmp / "device.csr"
        dev_cert = tmp / "device.crt"

        run(["openssl", "ecparam", "-genkey", "-name", "prime256v1",
             "-noout", "-out", str(dev_key)])
        run(["openssl", "req", "-new",
             "-key", str(dev_key),
             "-out", str(dev_csr),
             "-subj", "/CN=IEEE 2030.5 Dev Device/O=Development/C=US"])
        run(["openssl", "x509", "-req",
             "-in", str(dev_csr),
             "-CA", str(ca_cert),
             "-CAkey", str(ca_key),
             "-CAcreateserial",
             "-out", str(dev_cert),
             "-days", "3650"])

        # device.pem = cert + key in one file (what client_test expects for .pem)
        device_pem = out_dir / "device.pem"
        device_pem.write_bytes(
            dev_cert.read_bytes() + dev_key.read_bytes()
        )

        # CA cert into ca/ dir
        shutil.copy(ca_cert, ca_dir / "ca.pem")

    print(f"  {out_dir}/device.pem       (device cert + key)")
    print(f"  {out_dir}/ca/ca.pem        (CA certificate)")


# ---------------------------------------------------------------------------
# gateway.yaml SFDI update
# ---------------------------------------------------------------------------

def update_config_sfdi(config_path: Path, sfdi: int) -> None:
    """Patch the sfdi field in gateway.yaml in-place."""
    import re
    text = config_path.read_text()
    # Replace the sfdi value under the device: section
    updated = re.sub(
        r'(sfdi:\s*)["\']?[\d]+["\']?',
        f'sfdi: "{sfdi}"',
        text,
        count=1,
    )
    if updated == text:
        print(f"\nNote: could not auto-update sfdi in {config_path}. Set it manually.")
        return
    config_path.write_text(updated)
    print(f"\nUpdated {config_path}: device.sfdi = {sfdi}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate IEEE 2030.5 dev certificates")
    parser.add_argument(
        "--out", default="config/certs",
        help="Output directory for certificates (default: config/certs)",
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to gateway.yaml to update with computed SFDI",
    )
    args = parser.parse_args()

    if not shutil.which("openssl"):
        print("ERROR: openssl not found in PATH", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)

    print("Generating ECDSA P-256 certificates...")
    generate_certs(out_dir)

    device_pem = out_dir / "device.pem"
    lfdi_hex, sfdi = compute_sfdi(device_pem)

    print(f"\nDevice identity:")
    print(f"  LFDI : {lfdi_hex}")
    print(f"  SFDI : {sfdi}")

    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.exists():
            update_config_sfdi(cfg_path, sfdi)
        else:
            print(f"\nNote: {cfg_path} not found, skipping SFDI update.")

    print("\nDone. Add config/certs/ to .gitignore (already set).")
    print(f"Set device.sfdi: \"{sfdi}\" in your gateway.yaml if not auto-updated.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import base64
import secrets


def new_device_secret() -> str:
    """Return a URL-safe 256-bit device secret without padding."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def secret_bytes(value: str) -> bytes:
    text = str(value or "").strip()
    padding = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + padding)

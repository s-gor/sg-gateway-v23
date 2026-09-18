from __future__ import annotations

from dataclasses import asdict

from app.connections.settings import get_connection_settings
from app.sgnet.config import from_connection, ready


def overview() -> dict:
    current = from_connection(get_connection_settings("sgnet"))
    payload = asdict(current)
    payload["transports"] = list(current.transports)
    payload["ready"] = ready(current)
    return payload

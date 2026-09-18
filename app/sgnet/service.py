from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from app.connections.settings import get_connection_settings
from app.db import connect
from app.maintenance.operations import log_operation
from app.sgnet.config import from_connection, ready

DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


class SgNetSettingsError(ValueError):
    pass


def _domain(value: object) -> str:
    domain = str(value or "").strip().lower().rstrip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise SgNetSettingsError("Некорректное TLS-имя SG-Net")
    if "sgnet" in domain or "sg-net" in domain:
        raise SgNetSettingsError("TLS-имя не должно раскрывать название SG-Net")
    return domain


def _absolute_file(value: object, label: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise SgNetSettingsError(f"Не указан {label}")
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise SgNetSettingsError(f"Некорректный путь: {label}")
    return str(path)


def save_settings(values) -> dict:
    current = get_connection_settings("sgnet")
    enabled = str(values.get("enabled") or "").strip().lower() in {"1", "true", "on", "yes"}
    public_host = str(values.get("host") or current.host or "").strip()
    config = dict(current.config)

    if enabled:
        if not public_host:
            raise SgNetSettingsError("Не указан публичный адрес SG-Net")
        config["server_name"] = _domain(values.get("server_name"))
        config["certificate_path"] = _absolute_file(
            values.get("certificate_path"), "сертификат"
        )
        config["private_key_path"] = _absolute_file(
            values.get("private_key_path"), "private key"
        )
    else:
        config["server_name"] = str(values.get("server_name") or config.get("server_name") or "").strip().lower()
        config["certificate_path"] = str(
            values.get("certificate_path") or config.get("certificate_path") or ""
        ).strip()
        config["private_key_path"] = str(
            values.get("private_key_path") or config.get("private_key_path") or ""
        ).strip()

    config.update(
        {
            "protocol_version": 1,
            "internal_host": "127.0.0.1",
            "internal_port": 10448,
            "transports": ["sg-tls"],
        }
    )

    with connect() as connection:
        connection.execute(
            """
            UPDATE connection_settings
            SET enabled = ?, host = ?, port = 443, config_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE engine = 'sgnet'
            """,
            (
                1 if enabled else 0,
                public_host,
                json.dumps(config, ensure_ascii=False, sort_keys=True),
            ),
        )

    log_operation(
        action="connection.update",
        target="connection:sgnet",
        message=(
            f"SG-Net {'включён' if enabled else 'выключен'}; "
            f"public={public_host or 'not-configured'}:443; "
            f"tls_name={config.get('server_name') or 'not-configured'}"
        ),
    )
    return overview()


def overview() -> dict:
    current = from_connection(get_connection_settings("sgnet"))
    payload = asdict(current)
    payload["transports"] = list(current.transports)
    payload["ready"] = ready(current)
    # Never return private key contents or credential material. Paths are
    # administrative configuration and are safe to render to the owner.
    return payload

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.connections.settings import ConnectionSettings
from app.single_edge import PUBLIC_TCP_PORT, SGNET_INTERNAL_PORT


@dataclass(frozen=True)
class SgNetConfig:
    enabled: bool
    public_host: str
    public_port: int
    internal_host: str
    internal_port: int
    server_name: str
    certificate_path: str
    private_key_path: str
    protocol_version: int
    transports: tuple[str, ...]


def from_connection(settings: ConnectionSettings) -> SgNetConfig:
    config = dict(settings.config)
    return SgNetConfig(
        enabled=bool(settings.enabled),
        public_host=str(settings.host or "").strip(),
        public_port=PUBLIC_TCP_PORT,
        internal_host=str(config.get("internal_host") or "127.0.0.1"),
        internal_port=int(config.get("internal_port") or SGNET_INTERNAL_PORT),
        server_name=str(config.get("server_name") or "").strip(),
        certificate_path=str(config.get("certificate_path") or "").strip(),
        private_key_path=str(config.get("private_key_path") or "").strip(),
        protocol_version=int(config.get("protocol_version") or 1),
        transports=tuple(str(item) for item in config.get("transports", ["sg-tls"])),
    )


def ready(config: SgNetConfig) -> bool:
    return bool(
        config.enabled
        and config.public_host
        and config.server_name
        and config.internal_host == "127.0.0.1"
        and config.internal_port == SGNET_INTERNAL_PORT
        and config.protocol_version == 1
        and config.transports == ("sg-tls",)
        and Path(config.certificate_path).is_file()
        and Path(config.private_key_path).is_file()
    )

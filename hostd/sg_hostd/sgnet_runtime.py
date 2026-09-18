from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path

from app.connections.settings import get_connection_settings
from app.db import connect
from app.single_edge import SGNET_INTERNAL_PORT

DEFAULT_BINARY = Path("/usr/local/bin/sgnet-server")
DEFAULT_CONFIG = Path("/etc/sg-gateway/sgnet.json")
DEFAULT_PREVIOUS = Path("/etc/sg-gateway/sgnet.json.previous")
DEFAULT_HEALTH_SOCKET = Path("/run/sg-gateway/sgnet.sock")
DEFAULT_SERVICE = "sg-gateway-sgnet.service"
DEFAULT_EDGE_REFRESH = Path("/opt/sg-gateway/deploy/configure-panel-access.sh")


class SgNetRuntimeError(RuntimeError):
    pass


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result


def _device_rows() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT d.id AS device_id, dc.config_json
            FROM device_credentials dc
            JOIN devices d ON d.id = dc.device_id
            JOIN clients c ON c.id = d.client_id
            WHERE dc.engine = 'sgnet'
              AND d.enabled = 1
              AND c.enabled = 1
              AND dc.status != 'disabled'
            ORDER BY d.id
            """
        ).fetchall()

    devices: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row["config_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            continue
        secret = str(payload.get("secret") or "").strip()
        if not secret:
            continue
        devices.append(
            {
                "id": int(row["device_id"]),
                "secret": secret,
                "enabled": True,
            }
        )
    return devices


def build_runtime_document() -> dict:
    settings = get_connection_settings("sgnet")
    config = dict(settings.config)
    return {
        "version": 1,
        "listen": f"127.0.0.1:{SGNET_INTERNAL_PORT}",
        "tls": {
            "server_name": str(config.get("server_name") or "").strip(),
            "certificate": str(config.get("certificate_path") or "").strip(),
            "private_key": str(config.get("private_key_path") or "").strip(),
            "min_version": "1.3",
        },
        "health_socket": str(DEFAULT_HEALTH_SOCKET),
        "limits": {
            "max_sessions_per_device": 2,
            "max_streams_per_session": 512,
            "max_frame_payload": 1048576,
            "handshake_timeout_seconds": 10,
            "idle_timeout_seconds": 120,
            "drain_grace_seconds": 15,
        },
        "devices": _device_rows(),
    }


def _atomic_write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    candidate = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(candidate, 0o600)
        os.replace(candidate, path)
    finally:
        candidate.unlink(missing_ok=True)
    return path


def _refresh_single_edge(script: Path = DEFAULT_EDGE_REFRESH) -> None:
    if not script.is_file():
        raise SgNetRuntimeError("Single Edge refresh script is unavailable")
    result = _run([str(script), "--mode", "refresh"], timeout=120)
    if result.returncode != 0:
        raise SgNetRuntimeError("Single Edge refresh failed")


def _service_active(service: str = DEFAULT_SERVICE) -> bool:
    return _run(["systemctl", "is-active", "--quiet", service], timeout=10).returncode == 0


def _validate_candidate(candidate: Path, binary: Path = DEFAULT_BINARY) -> None:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SgNetRuntimeError("SG-Net runtime binary is not installed")
    result = _run([str(binary), "--check-config", str(candidate)])
    if result.returncode != 0:
        raise SgNetRuntimeError("SG-Net candidate configuration validation failed")


def _health(socket_path: Path = DEFAULT_HEALTH_SOCKET) -> dict:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(socket_path))
            chunks: list[bytes] = []
            while True:
                data = client.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if sum(map(len, chunks)) > 1024 * 1024:
                    raise SgNetRuntimeError("SG-Net health response too large")
    except OSError as exc:
        raise SgNetRuntimeError("SG-Net health socket is unavailable") from exc

    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise SgNetRuntimeError("SG-Net health response is invalid") from exc
    if not isinstance(payload, dict):
        raise SgNetRuntimeError("SG-Net health response is invalid")
    allowed = {
        "runtime_version",
        "protocol_version",
        "listener",
        "active_sessions",
        "active_streams",
        "uptime_seconds",
        "auth_failures",
    }
    return {key: payload[key] for key in allowed if key in payload}


def test_candidate(
    *,
    candidate: Path = Path("/etc/sg-gateway/sgnet.json.new"),
    binary: Path = DEFAULT_BINARY,
) -> dict:
    settings = get_connection_settings("sgnet")
    if not settings.enabled:
        return {"ok": True, "enabled": False, "message": "SG-Net disabled"}
    _atomic_write(candidate, build_runtime_document())
    _validate_candidate(candidate, binary)
    return {
        "ok": True,
        "enabled": True,
        "message": "SG-Net candidate valid",
        "device_count": len(_device_rows()),
    }


def apply(
    *,
    config_path: Path = DEFAULT_CONFIG,
    previous_path: Path = DEFAULT_PREVIOUS,
    candidate_path: Path = Path("/etc/sg-gateway/sgnet.json.new"),
    binary: Path = DEFAULT_BINARY,
    service: str = DEFAULT_SERVICE,
    health_socket: Path = DEFAULT_HEALTH_SOCKET,
) -> dict:
    settings = get_connection_settings("sgnet")
    was_active = _service_active(service)
    previous = config_path.read_bytes() if config_path.is_file() else None

    if not settings.enabled:
        stop = _run(["systemctl", "stop", service], timeout=30)
        if stop.returncode != 0:
            raise SgNetRuntimeError("Failed to stop disabled SG-Net service")
        _refresh_single_edge()
        return {"ok": True, "enabled": False, "message": "SG-Net disabled"}

    _atomic_write(candidate_path, build_runtime_document())
    _validate_candidate(candidate_path, binary)

    if previous is not None:
        previous_path.parent.mkdir(parents=True, exist_ok=True)
        previous_path.write_bytes(previous)
        os.chmod(previous_path, 0o600)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate_path, config_path)
    os.chmod(config_path, 0o600)

    try:
        restart = _run(["systemctl", "restart", service], timeout=30)
        if restart.returncode != 0:
            raise SgNetRuntimeError("Failed to restart SG-Net service")
        payload = _health(health_socket)
        _refresh_single_edge()
        return {
            "ok": True,
            "enabled": True,
            "message": "SG-Net runtime applied",
            "health": payload,
        }
    except Exception:
        if previous is None:
            config_path.unlink(missing_ok=True)
        else:
            config_path.write_bytes(previous)
            os.chmod(config_path, 0o600)
        if was_active and config_path.is_file():
            _run(["systemctl", "restart", service], timeout=30)
        else:
            _run(["systemctl", "stop", service], timeout=30)
        raise


def rollback(
    *,
    config_path: Path = DEFAULT_CONFIG,
    previous_path: Path = DEFAULT_PREVIOUS,
    service: str = DEFAULT_SERVICE,
    health_socket: Path = DEFAULT_HEALTH_SOCKET,
) -> dict:
    if not previous_path.is_file():
        raise SgNetRuntimeError("No previous SG-Net configuration")
    previous = previous_path.read_bytes()
    config_path.write_bytes(previous)
    os.chmod(config_path, 0o600)
    result = _run(["systemctl", "restart", service], timeout=30)
    if result.returncode != 0:
        raise SgNetRuntimeError("Failed to restart SG-Net service after rollback")
    return {
        "ok": True,
        "message": "SG-Net runtime rolled back",
        "health": _health(health_socket),
    }


def restart(
    *,
    service: str = DEFAULT_SERVICE,
    health_socket: Path = DEFAULT_HEALTH_SOCKET,
) -> dict:
    result = _run(["systemctl", "restart", service], timeout=30)
    if result.returncode != 0:
        raise SgNetRuntimeError("Failed to restart SG-Net service")
    return {"ok": True, "message": "SG-Net runtime restarted", "health": _health(health_socket)}


def status(
    *,
    service: str = DEFAULT_SERVICE,
    health_socket: Path = DEFAULT_HEALTH_SOCKET,
) -> dict:
    settings = get_connection_settings("sgnet")
    payload = {
        "enabled": bool(settings.enabled),
        "service_active": _service_active(service),
        "public_port": 443,
        "server_name_configured": bool(str(settings.config.get("server_name") or "").strip()),
        "internal_listener": f"127.0.0.1:{SGNET_INTERNAL_PORT}",
    }
    if payload["service_active"]:
        try:
            payload["health"] = _health(health_socket)
        except SgNetRuntimeError:
            payload["health"] = {"ready": False}
    return payload

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class CascadeError(RuntimeError):
    pass


CASCADE_CORE_TAG = "cascade-core"
CASCADE_ROUTING_TAGS = {"cascade4", "cascade6"}
_ALLOWED_PROTOCOLS = {"vless"}


def state_path() -> Path:
    explicit = os.getenv("SG_GATEWAY_CASCADE_STATE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    from app.config import load_config

    return load_config().data_dir / "cascade.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_state() -> dict:
    try:
        payload = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _clone(value: object) -> object:
    return json.loads(json.dumps(value))


def normalize_outbound(document: object) -> dict:
    """Validate a Gateway-B Xray outbound and reserve the SG Cascade tag.

    23.02 deliberately starts with VLESS because Gateway A must have one
    deterministic, testable server-to-server transport before more protocols
    are added. The complete outbound settings remain Xray-native, so Reality,
    TLS and transport parameters are preserved rather than re-invented here.
    """
    if not isinstance(document, dict):
        raise CascadeError("Cascade outbound должен быть JSON-объектом")

    result = _clone(document)
    assert isinstance(result, dict)
    protocol = str(result.get("protocol") or "").strip().lower()
    if protocol not in _ALLOWED_PROTOCOLS:
        raise CascadeError("Cascade 23.02 пока поддерживает только VLESS outbound")

    settings = result.get("settings")
    if not isinstance(settings, dict):
        raise CascadeError("Cascade VLESS outbound не содержит settings")
    vnext = settings.get("vnext")
    if not isinstance(vnext, list) or not vnext or not isinstance(vnext[0], dict):
        raise CascadeError("Cascade VLESS outbound не содержит vnext")

    peer = vnext[0]
    address = str(peer.get("address") or "").strip()
    try:
        port = int(peer.get("port") or 0)
    except (TypeError, ValueError) as exc:
        raise CascadeError("Cascade VLESS outbound содержит неверный port") from exc
    users = peer.get("users")
    if not address or port < 1 or port > 65535:
        raise CascadeError("Cascade VLESS outbound содержит неверный endpoint")
    if not isinstance(users, list) or not users or not isinstance(users[0], dict):
        raise CascadeError("Cascade VLESS outbound не содержит пользователя")
    if not str(users[0].get("id") or "").strip():
        raise CascadeError("Cascade VLESS outbound не содержит UUID")

    # A cascade outbound is an egress only. Never accept fields that can alter
    # the local Gateway-A routing graph.
    for forbidden in ("routing", "inbounds", "dns"):
        result.pop(forbidden, None)
    result["tag"] = CASCADE_CORE_TAG
    return result


def configure(
    document: object,
    *,
    name: str = "Gateway B",
    ipv4_ready: bool = True,
    ipv6_ready: bool = False,
) -> dict:
    normalized = normalize_outbound(document)
    payload = {
        "enabled": True,
        "name": str(name or "Gateway B").strip() or "Gateway B",
        "outbound": normalized,
        "families": {
            "ipv4": bool(ipv4_ready),
            "ipv6": bool(ipv6_ready),
        },
        "updated_at": _utc_now(),
    }
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def enable() -> dict:
    payload = _read_state()
    if not payload or payload.get("outbound") is None:
        raise CascadeError("Каскад ещё не настроен")
    normalize_outbound(payload.get("outbound"))
    families = payload.get("families")
    if not isinstance(families, dict) or not any(bool(families.get(key)) for key in ("ipv4", "ipv6")):
        raise CascadeError("Для Каскада не выбрано ни одного семейства IP")
    payload["enabled"] = True
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def disable() -> dict:
    payload = _read_state()
    if not payload:
        return overview()
    payload["enabled"] = False
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def family_capabilities() -> dict[str, bool]:
    state = _read_state()
    if not bool(state.get("enabled")):
        return {"ipv4": False, "ipv6": False}
    families = state.get("families")
    if not isinstance(families, dict):
        return {"ipv4": False, "ipv6": False}
    return {
        "ipv4": bool(families.get("ipv4")),
        "ipv6": bool(families.get("ipv6")),
    }


def enabled() -> bool:
    state = _read_state()
    if not bool(state.get("enabled")):
        return False
    try:
        normalize_outbound(state.get("outbound"))
    except CascadeError:
        return False
    return any(family_capabilities().values())


def outbound(*, require_enabled: bool = True) -> dict | None:
    state = _read_state()
    if require_enabled and not enabled():
        return None
    raw = state.get("outbound")
    if raw is None:
        return None
    return normalize_outbound(raw)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_connection(*, timeout: int = 25) -> dict:
    """Send real HTTP traffic through Gateway B using an ephemeral local SOCKS inbound."""
    state = _read_state()
    document = normalize_outbound(state.get("outbound"))
    xray = shutil.which("xray") or (
        "/usr/local/bin/xray" if Path("/usr/local/bin/xray").is_file() else None
    )
    curl = shutil.which("curl")
    if not xray:
        raise CascadeError("Xray не найден: реальная проверка Каскада невозможна")
    if not curl:
        raise CascadeError("curl не найден: реальная проверка Каскада невозможна")

    port = _free_local_port()
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "cascade-test-in",
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [document],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["cascade-test-in"],
                    "outboundTag": CASCADE_CORE_TAG,
                }
            ],
        },
    }

    with tempfile.TemporaryDirectory(prefix="sg-gateway-cascade-test-") as directory:
        config_path = Path(directory) / "config.json"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [str(xray), "run", "-config", str(config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 6
            ready = False
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.1)
            if not ready:
                stderr = ""
                if process.poll() is not None and process.stderr:
                    stderr = process.stderr.read().strip()
                raise CascadeError(
                    "Тестовый Xray не поднял локальный SOCKS"
                    + (f": {stderr}" if stderr else "")
                )

            results: dict[str, dict] = {}
            for family, url in (
                ("ipv4", "https://api4.ipify.org"),
                ("ipv6", "https://api6.ipify.org"),
            ):
                command = [
                    str(curl),
                    "-4" if family == "ipv4" else "-6",
                    "--silent",
                    "--show-error",
                    "--fail",
                    "--max-time",
                    str(max(5, min(timeout, 20))),
                    "--socks5-hostname",
                    f"127.0.0.1:{port}",
                    url,
                ]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                ip = (result.stdout or "").strip()
                ok = result.returncode == 0 and bool(ip)
                results[family] = {
                    "ok": ok,
                    "ip": ip if ok else "",
                    "message": "Соединение через второй SG-Gateway подтверждено"
                    if ok
                    else (result.stderr or result.stdout or "Проверка не пройдена").strip(),
                }
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    payload = _read_state()
    payload["last_test"] = {
        "ok": bool(results["ipv4"]["ok"] or results["ipv6"]["ok"]),
        "ipv4": results["ipv4"],
        "ipv6": results["ipv6"],
        "checked_at": _utc_now(),
    }
    # Availability is derived from a real end-to-end request, not from a UI
    # checkbox. A failed family becomes unavailable to Routing until re-tested.
    payload["families"] = {
        "ipv4": bool(results["ipv4"]["ok"]),
        "ipv6": bool(results["ipv6"]["ok"]),
    }
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def overview() -> dict:
    state = _read_state()
    families = family_capabilities()
    active = enabled()
    outbound_doc = None
    endpoint = ""
    protocol = ""
    try:
        outbound_doc = normalize_outbound(state.get("outbound")) if state.get("outbound") else None
    except CascadeError:
        outbound_doc = None
    if outbound_doc:
        protocol = str(outbound_doc.get("protocol") or "")
        settings = outbound_doc.get("settings")
        vnext = settings.get("vnext") if isinstance(settings, dict) else None
        if isinstance(vnext, list) and vnext and isinstance(vnext[0], dict):
            host = str(vnext[0].get("address") or "")
            port = int(vnext[0].get("port") or 0)
            endpoint = f"{host}:{port}" if host and port else host
    return {
        "configured": outbound_doc is not None,
        "enabled": active,
        "name": str(state.get("name") or "Gateway B"),
        "endpoint": endpoint,
        "protocol": protocol,
        "ipv4_ready": bool(families["ipv4"]),
        "ipv6_ready": bool(families["ipv6"]),
        "updated_at": str(state.get("updated_at") or ""),
        "last_test": state.get("last_test") if isinstance(state.get("last_test"), dict) else {},
    }

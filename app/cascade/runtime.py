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

from app.cascade.bundle import CHANNEL_SPECS, CascadeBundleError, validate_bundle


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



CHANNEL_IDS = tuple(item[0] for item in CHANNEL_SPECS)
DEFAULT_PRIORITY = list(CHANNEL_IDS)
XRAY_ROUTABLE_CHANNELS = {"reality_tcp", "xhttp_reality", "xhttp_tls", "hysteria2"}
VALID_MODES = {"auto", "manual", "priority"}


def _channel_map(state: dict | None = None) -> dict[str, dict]:
    payload = state if isinstance(state, dict) else _read_state()
    raw = payload.get("channels")
    return raw if isinstance(raw, dict) else {}


def _choose_active_channel(state: dict) -> str:
    channels = _channel_map(state)
    ready = {
        key for key, value in channels.items()
        if isinstance(value, dict) and value.get("ready") and value.get("routable")
    }
    if not ready:
        return ""
    mode = str(state.get("mode") or "auto")
    if mode == "manual":
        manual = str(state.get("manual_channel") or "")
        return manual if manual in ready else ""
    priority = state.get("priority")
    order = priority if isinstance(priority, list) else DEFAULT_PRIORITY
    return next((str(item) for item in order if str(item) in ready), sorted(ready)[0])


def import_bundle(document: object, *, name: str = "Gateway B", ipv4_ready: bool = True, ipv6_ready: bool = False) -> dict:
    try:
        parsed = validate_bundle(document)
    except CascadeBundleError as exc:
        raise CascadeError(str(exc)) from exc
    rows = {str(item["id"]): dict(item) for item in parsed["channels"]}
    channels = {}
    for channel_id, title, kind, engine in CHANNEL_SPECS:
        row = rows.get(channel_id)
        channels[channel_id] = {
            "id": channel_id,
            "title": title,
            "kind": kind,
            "engine": engine,
            "payload": str(row.get("payload") or "") if row else "",
            "status": "unchecked" if row else "missing",
            "ready": False,
            "routable": channel_id in XRAY_ROUTABLE_CHANNELS,
            "last_test": {},
        }
    payload = {
        "format": "sg-cascade-state-v2",
        "enabled": False,
        "name": str(name or "Gateway B").strip() or "Gateway B",
        "mode": "auto",
        "priority": list(DEFAULT_PRIORITY),
        "manual_channel": "",
        "active_channel": "",
        "bundle_created_at": str(parsed.get("created_at") or ""),
        "bundle_complete": bool(parsed.get("complete")),
        "channels": channels,
        "requested_families": {"ipv4": bool(ipv4_ready), "ipv6": bool(ipv6_ready)},
        "families": {"ipv4": False, "ipv6": False},
        "last_test": {},
        "updated_at": _utc_now(),
    }
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def set_mode(mode: str, *, manual_channel: str = "", priority: list[str] | None = None) -> dict:
    payload = _read_state()
    selected = str(mode or "").strip().lower()
    if selected not in VALID_MODES:
        raise CascadeError("Неизвестный режим Каскада")
    if priority is not None:
        cleaned = []
        for item in priority:
            token = str(item or "").strip()
            if token in CHANNEL_IDS and token not in cleaned:
                cleaned.append(token)
        cleaned.extend(item for item in CHANNEL_IDS if item not in cleaned)
        payload["priority"] = cleaned
    if selected == "manual":
        manual = str(manual_channel or "").strip()
        if manual not in CHANNEL_IDS:
            raise CascadeError("Выберите канал для ручного режима")
        payload["manual_channel"] = manual
    payload["mode"] = selected
    payload["active_channel"] = _choose_active_channel(payload)
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def test_all_channels(*, timeout: int = 25) -> dict:
    payload = _read_state()
    channels = _channel_map(payload)
    if not channels:
        raise CascadeError("Сначала импортируйте Cascade bundle второго сервера")
    from app.cascade.channel_test import test_channel
    for channel_id in CHANNEL_IDS:
        item = channels.get(channel_id)
        if not isinstance(item, dict) or not str(item.get("payload") or "").strip():
            if isinstance(item, dict):
                item["status"] = "missing"
                item["ready"] = False
            continue
        item["status"] = "checking"
        item["ready"] = False
        _atomic_write_json(state_path(), payload, 0o600)
        try:
            result = test_channel(item, timeout=timeout)
            ipv4 = result.get("ipv4") if isinstance(result, dict) else {}
            ipv6 = result.get("ipv6") if isinstance(result, dict) else {}
            ok = bool(
                (isinstance(ipv4, dict) and ipv4.get("ok"))
                or (isinstance(ipv6, dict) and ipv6.get("ok"))
            )
            item["last_test"] = {
                "ok": ok,
                "ipv4": ipv4 if isinstance(ipv4, dict) else {},
                "ipv6": ipv6 if isinstance(ipv6, dict) else {},
                "checked_at": _utc_now(),
            }
            item["ready"] = ok
            item["status"] = "ready" if ok else "error"
        except Exception as exc:
            item["last_test"] = {"ok": False, "message": str(exc), "checked_at": _utc_now()}
            item["ready"] = False
            item["status"] = "error"
    ready_items = [item for item in channels.values() if isinstance(item, dict) and item.get("ready")]
    requested = payload.get("requested_families")
    requested = requested if isinstance(requested, dict) else {"ipv4": True, "ipv6": False}
    payload["families"] = {
        "ipv4": bool(requested.get("ipv4")) and any(bool((item.get("last_test") or {}).get("ipv4", {}).get("ok")) for item in ready_items),
        "ipv6": bool(requested.get("ipv6")) and any(bool((item.get("last_test") or {}).get("ipv6", {}).get("ok")) for item in ready_items),
    }
    payload["active_channel"] = _choose_active_channel(payload)
    payload["last_test"] = {
        "ok": len(ready_items) == len(CHANNEL_IDS),
        "ready_count": len(ready_items),
        "required_count": len(CHANNEL_IDS),
        "checked_at": _utc_now(),
    }
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def _multi_channel_enabled(state: dict) -> bool:
    if not bool(state.get("enabled")):
        return False
    channels = _channel_map(state)
    return bool(channels) and all(
        isinstance(channels.get(channel_id), dict) and channels[channel_id].get("ready")
        for channel_id in CHANNEL_IDS
    ) and bool(_choose_active_channel(state))

def configure(
    document: object,
    *,
    name: str = "Gateway B",
    ipv4_ready: bool = True,
    ipv6_ready: bool = False,
) -> dict:
    normalized = normalize_outbound(document)
    payload = {
        "enabled": False,
        "name": str(name or "Gateway B").strip() or "Gateway B",
        "outbound": normalized,
        "requested_families": {
            "ipv4": bool(ipv4_ready),
            "ipv6": bool(ipv6_ready),
        },
        # Readiness is earned only by test_connection(); saving JSON alone
        # must never make a Cascade route selectable.
        "families": {"ipv4": False, "ipv6": False},
        "last_test": {},
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
    requested = payload.get("requested_families")
    requested = requested if isinstance(requested, dict) else {"ipv4": True, "ipv6": False}
    payload["families"] = {
        "ipv4": bool(requested.get("ipv4")) and bool(results["ipv4"]["ok"]),
        "ipv6": bool(requested.get("ipv6")) and bool(results["ipv6"]["ok"]),
    }
    payload["updated_at"] = _utc_now()
    _atomic_write_json(state_path(), payload, 0o600)
    return overview()


def overview() -> dict:
    state = _read_state()
    stored_families = state.get("families")
    stored_families = stored_families if isinstance(stored_families, dict) else {}
    families = {
        "ipv4": bool(stored_families.get("ipv4")),
        "ipv6": bool(stored_families.get("ipv6")),
    }
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
        "ipv4_requested": bool((state.get("requested_families") or {}).get("ipv4", True))
        if isinstance(state.get("requested_families") or {}, dict) else True,
        "ipv6_requested": bool((state.get("requested_families") or {}).get("ipv6", False))
        if isinstance(state.get("requested_families") or {}, dict) else False,
        "updated_at": str(state.get("updated_at") or ""),
        "last_test": state.get("last_test") if isinstance(state.get("last_test"), dict) else {},
    }

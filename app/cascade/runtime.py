from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


class CascadeError(RuntimeError):
    pass


CASCADE_CORE_TAG = "cascade-core"
CASCADE_ROUTING_TAGS = {"cascade4", "cascade6"}
_ALLOWED_PROTOCOLS = {"vless"}


def state_path() -> Path:
    return Path(
        os.getenv(
            "SG_GATEWAY_CASCADE_STATE_PATH",
            "/etc/sg-gateway/cascade.json",
        )
    )


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
    }

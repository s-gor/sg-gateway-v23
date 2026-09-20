from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path


class ExternalOutboundError(RuntimeError):
    pass


def state_path() -> Path:
    return Path(os.getenv("SG_GATEWAY_EXTERNAL_OUTBOUNDS_PATH", "/etc/sg-gateway/xray-external-outbounds.json"))


def _empty() -> dict:
    return {"outbounds": [], "groups": []}


def _read() -> dict:
    path = state_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ExternalOutboundError(f"Не удалось прочитать External Outbounds: {exc}") from exc
    if not isinstance(value, dict):
        raise ExternalOutboundError("External Outbounds: неверный формат состояния")
    value.setdefault("outbounds", [])
    value.setdefault("groups", [])
    if not isinstance(value["outbounds"], list) or not isinstance(value["groups"], list):
        raise ExternalOutboundError("External Outbounds: неверный формат списков")
    return value


def _write(value: dict) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _slug(value: str) -> str:
    token = re.sub(r"[^a-z0-9-]+", "-", str(value or "").strip().lower()).strip("-")
    token = re.sub(r"-{2,}", "-", token)
    if not token:
        token = uuid.uuid4().hex[:8]
    return token[:40]


def outbound_tag(identifier: str) -> str:
    return f"ext-{_slug(identifier)}"


def group_tag(identifier: str) -> str:
    return f"group-{_slug(identifier)}"


def _normalize_host(value: object) -> str:
    host = str(value or "").strip()
    if not host or any(ch.isspace() for ch in host):
        raise ExternalOutboundError("Укажите корректный host")
    if len(host) > 253:
        raise ExternalOutboundError("Host слишком длинный")
    return host


def _normalize_port(value: object) -> int:
    try:
        port = int(str(value or "").strip())
    except ValueError as exc:
        raise ExternalOutboundError("Укажите корректный порт") from exc
    if not 1 <= port <= 65535:
        raise ExternalOutboundError("Порт должен быть от 1 до 65535")
    return port


def _normalize_protocol(value: object) -> str:
    protocol = str(value or "").strip().lower()
    if protocol not in {"socks", "http"}:
        raise ExternalOutboundError("Поддерживаются SOCKS5 и HTTP CONNECT")
    return protocol


def _normalize_name(value: object) -> str:
    name = str(value or "").strip()
    if not name:
        raise ExternalOutboundError("Укажите название выхода")
    return name[:80]


def list_outbounds() -> list[dict]:
    value = _read()
    result: list[dict] = []
    for raw in value["outbounds"]:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["tag"] = outbound_tag(str(item.get("id") or ""))
        item["has_password"] = bool(item.get("password"))
        item.pop("password", None)
        result.append(item)
    return result


def list_groups() -> list[dict]:
    value = _read()
    result: list[dict] = []
    for raw in value["groups"]:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["tag"] = group_tag(str(item.get("id") or ""))
        result.append(item)
    return result


def routing_tags() -> set[str]:
    return {
        outbound_tag(str(item.get("id") or ""))
        for item in _read()["outbounds"]
        if isinstance(item, dict) and item.get("enabled", True)
    }


def save_outbound(*, name: str, protocol: str, host: str, port: object, username: str = "", password: str = "") -> dict:
    value = _read()
    normalized_name = _normalize_name(name)
    normalized_protocol = _normalize_protocol(protocol)
    normalized_host = _normalize_host(host)
    normalized_port = _normalize_port(port)
    identifier = _slug(normalized_name)
    existing_ids = {str(item.get("id") or "") for item in value["outbounds"] if isinstance(item, dict)}
    base = identifier
    counter = 2
    while identifier in existing_ids:
        identifier = f"{base}-{counter}"
        counter += 1
    item = {
        "id": identifier,
        "name": normalized_name,
        "protocol": normalized_protocol,
        "host": normalized_host,
        "port": normalized_port,
        "username": str(username or "").strip(),
        "password": str(password or ""),
        "enabled": True,
    }
    value["outbounds"].append(item)
    _write(value)
    public = dict(item)
    public["tag"] = outbound_tag(identifier)
    public["has_password"] = bool(public.pop("password", ""))
    return public


def remove_outbound(identifier: str) -> None:
    value = _read()
    identifier = str(identifier or "").strip()
    before = len(value["outbounds"])
    value["outbounds"] = [
        item for item in value["outbounds"]
        if not isinstance(item, dict) or str(item.get("id") or "") != identifier
    ]
    if len(value["outbounds"]) == before:
        raise ExternalOutboundError("External outbound не найден")
    for group in value["groups"]:
        if isinstance(group, dict):
            group["members"] = [member for member in group.get("members", []) if member != outbound_tag(identifier)]
    _write(value)


def build_xray_outbounds() -> list[dict]:
    result: list[dict] = []
    for raw in _read()["outbounds"]:
        if not isinstance(raw, dict) or not raw.get("enabled", True):
            continue
        protocol = _normalize_protocol(raw.get("protocol"))
        server: dict = {
            "address": _normalize_host(raw.get("host")),
            "port": _normalize_port(raw.get("port")),
        }
        username = str(raw.get("username") or "").strip()
        password = str(raw.get("password") or "")
        if username or password:
            server["users"] = [{"user": username, "pass": password}]
        result.append({
            "tag": outbound_tag(str(raw.get("id") or "")),
            "protocol": protocol,
            "settings": {"servers": [server]},
        })
    return result


def overview() -> dict:
    outbounds = list_outbounds()
    groups = list_groups()
    return {
        "outbounds": outbounds,
        "groups": groups,
        "count": len(outbounds),
        "group_count": len(groups),
        "routing_tags": sorted(item["tag"] for item in outbounds if item.get("enabled", True)),
    }


def _restore_state(snapshot: dict) -> None:
    _write(snapshot)


def _tag_in_active_routing(tag: str) -> bool:
    try:
        from app.routing.runtime import load_managed_fragment
        rules = load_managed_fragment().get("routing", {}).get("rules", [])
    except Exception:
        return False
    return any(
        isinstance(rule, dict) and str(rule.get("outboundTag") or "") == tag
        for rule in rules
    )


def apply_runtime() -> dict:
    from app.routing.runtime import (
        RoutingRuntimeError,
        atomic_write_json,
        build_full_config,
        restart_xray,
        service_is_active,
        xray_config_path,
        xray_test_config,
    )

    path = xray_config_path()
    previous = None
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            previous = None
    candidate = build_full_config(base_config=previous if isinstance(previous, dict) else None)
    status, message = xray_test_config(candidate)
    if status == "error":
        raise ExternalOutboundError(message)
    was_active = service_is_active()
    atomic_write_json(path, candidate, 0o600)
    if was_active:
        restart_status, restart_message = restart_xray(required=True)
        if restart_status == "error":
            if isinstance(previous, dict):
                atomic_write_json(path, previous, 0o600)
                restart_xray(required=False)
            raise ExternalOutboundError(restart_message)
    return {"ok": True, "message": message}


def create_and_apply(**kwargs) -> dict:
    snapshot = _read()
    item = save_outbound(**kwargs)
    try:
        runtime = apply_runtime()
    except Exception:
        _restore_state(snapshot)
        raise
    return {"outbound": item, "runtime": runtime}


def remove_and_apply(identifier: str) -> dict:
    tag = outbound_tag(identifier)
    if _tag_in_active_routing(tag):
        raise ExternalOutboundError(
            "Этот outbound используется активным Routing. Сначала замените правила."
        )
    snapshot = _read()
    remove_outbound(identifier)
    try:
        runtime = apply_runtime()
    except Exception:
        _restore_state(snapshot)
        raise
    return {"ok": True, "runtime": runtime}

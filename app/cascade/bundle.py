from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from app.clients.exports import build_protocol_export, protocol_ready
from app.clients.repository import (
    create_client,
    get_client,
    get_primary_device,
    list_clients,
)
from app.clients.runtime import ClientWorkflowError, apply_clients_runtime


SERVICE_CLIENT_NAME = "SG Cascade Service"
BUNDLE_FORMAT = "sg-cascade-bundle-v1"
SERVICE_ACCESS = ",".join(
    (
        "amneziawg31",
        "xray_reality_tcp",
        "xray_xhttp_reality",
        "xray_xhttp_tls",
        "xray_hysteria2",
        "mihomo",
        "anytls",
        "tuic",
        "naiveproxy",
    )
)

CHANNEL_SPECS = (
    ("reality_tcp", "Reality TCP", "xray-reality-tcp", "Xray"),
    ("xhttp_reality", "XHTTP Reality", "xray-xhttp-reality", "Xray"),
    ("xhttp_tls", "XHTTP TLS", "xray-xhttp-tls", "Xray"),
    ("hysteria2", "Hysteria2", "hysteria2", "Xray"),
    ("awg31", "AmneziaWG 3.1", "amneziawg31-uri", "AWG"),
    ("mieru", "Mieru", "mieru", "Mihomo"),
    ("anytls", "AnyTLS", "anytls", "sing-box"),
    ("tuic", "TUIC", "tuic", "sing-box"),
    ("naiveproxy", "NaiveProxy", "naiveproxy", "NaiveProxy"),
)


class CascadeBundleError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _service_client():
    for client in list_clients():
        if client.name == SERVICE_CLIENT_NAME:
            return client
    client_id = create_client(SERVICE_CLIENT_NAME, SERVICE_ACCESS)
    if not client_id:
        raise CascadeBundleError("Не удалось создать служебный доступ Каскада")
    client = get_client(client_id)
    if client is None:
        raise CascadeBundleError("Служебный клиент Каскада не найден после создания")
    return client


def ensure_service_bundle() -> dict:
    client = _service_client()
    device = get_primary_device(client.id)
    if device is None:
        raise CascadeBundleError("У служебного клиента Каскада нет основного устройства")

    try:
        apply_clients_runtime()
    except ClientWorkflowError as exc:
        raise CascadeBundleError(str(exc)) from exc

    # Re-read after runtime apply so deployment statuses are current.
    client = get_client(client.id) or client
    device = get_primary_device(client.id) or device
    channels: list[dict] = []
    for channel_id, title, kind, engine in CHANNEL_SPECS:
        ready = False
        payload = ""
        error = ""
        try:
            ready = bool(protocol_ready(client, kind, device))
            if ready:
                payload = str(build_protocol_export(client, kind, device).body or "").strip()
                ready = bool(payload)
        except Exception as exc:
            error = str(exc)
            ready = False
        channels.append(
            {
                "id": channel_id,
                "title": title,
                "kind": kind,
                "engine": engine,
                "ready": ready,
                "payload": payload if ready else "",
                "error": error,
            }
        )

    ready_count = sum(1 for item in channels if item["ready"])
    return {
        "format": BUNDLE_FORMAT,
        "created_at": _utc_now(),
        "service_client_id": client.id,
        "device_id": device.id,
        "ready_count": ready_count,
        "required_count": len(CHANNEL_SPECS),
        "ready": ready_count == len(CHANNEL_SPECS),
        "channels": channels,
    }


def public_bundle(bundle: dict) -> dict:
    """Bundle is intentionally portable; it contains only client-side credentials."""
    return {
        "format": BUNDLE_FORMAT,
        "created_at": str(bundle.get("created_at") or _utc_now()),
        "channels": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "kind": str(item.get("kind") or ""),
                "engine": str(item.get("engine") or ""),
                "payload": str(item.get("payload") or ""),
            }
            for item in bundle.get("channels", [])
            if isinstance(item, dict) and item.get("ready") and item.get("payload")
        ],
    }


def validate_bundle(document: object) -> dict:
    if not isinstance(document, dict) or document.get("format") != BUNDLE_FORMAT:
        raise CascadeBundleError("Это не SG Cascade bundle")
    rows = document.get("channels")
    if not isinstance(rows, list):
        raise CascadeBundleError("Cascade bundle не содержит список channels")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        channel_id = str(row.get("id") or "").strip()
        payload = str(row.get("payload") or "").strip()
        if channel_id and payload:
            by_id[channel_id] = {
                "id": channel_id,
                "title": str(row.get("title") or channel_id),
                "kind": str(row.get("kind") or ""),
                "engine": str(row.get("engine") or ""),
                "payload": payload,
            }
    expected = {item[0] for item in CHANNEL_SPECS}
    return {
        "format": BUNDLE_FORMAT,
        "created_at": str(document.get("created_at") or ""),
        "channels": [by_id[key] for key in expected if key in by_id],
        "present": sorted(expected & set(by_id)),
        "missing": sorted(expected - set(by_id)),
        "complete": expected <= set(by_id),
    }


def dumps_bundle(bundle: dict) -> str:
    return json.dumps(public_bundle(bundle), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

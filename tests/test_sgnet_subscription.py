from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import app.clients.sg_subscription as sub
from app.clients.exports import ClientExport
from app.clients.repository import Client


def _client():
    return Client(
        id=1,
        name="Alice",
        enabled=True,
        expires_at=None,
        awg_status="missing",
        xray_status="missing",
    )


def _device():
    return SimpleNamespace(
        id=10,
        name="Phone",
        is_primary=True,
        enabled=True,
        expires_at=None,
    )


def _wire(monkeypatch):
    monkeypatch.setattr(sub, "list_devices", lambda client_id: [_device()])
    monkeypatch.setattr(sub, "device_access_tokens", lambda device_id: ["sgnet"])
    monkeypatch.setattr(sub, "protocol_ready", lambda client, kind, device: kind == "sgnet")
    monkeypatch.setattr(
        sub,
        "build_protocol_export",
        lambda client, kind, device: ClientExport(
            "sg-net.json",
            "application/vnd.sg.net+json",
            json.dumps({
                "type": "sg-net",
                "protocol_version": 1,
                "device_id": 10,
                "secret": "private-secret",
                "server": "vpn.example.com",
                "port": 443,
                "server_name": "edge.example.com",
                "transports": ["sg-tls"],
            }),
        ),
    )


def test_sg_native_json_contains_private_sgnet_profile(monkeypatch):
    _wire(monkeypatch)
    document = sub.build_sg_subscription_document(_client())
    profiles = document["devices"][0]["profiles"]
    assert len(profiles) == 1
    assert profiles[0]["id"] == "sgnet"
    assert profiles[0]["protocol"] == "sg-net"
    assert profiles[0]["format"] == "config"
    payload = json.loads(profiles[0]["config"])
    assert payload["secret"] == "private-secret"


def test_compatible_base64_feed_excludes_sgnet(monkeypatch):
    _wire(monkeypatch)
    body = sub.build_compatible_subscription_body(_client())
    decoded = base64.b64decode(body).decode("utf-8")
    assert "sgnet" not in decoded.lower()
    assert "private-secret" not in decoded


def test_router_json_excludes_sgnet(monkeypatch):
    _wire(monkeypatch)
    document = sub.build_router_subscription_document(_client(), 10)
    assert document is not None
    assert document["profiles"] == []


def test_sg_text_keeps_private_config_inside_sg_envelope(monkeypatch):
    _wire(monkeypatch)
    body = sub.build_sg_subscription_text(_client())
    assert "# SG-SUBSCRIPTION/1" in body
    assert "# SG-CONFIG " in body
    assert "sgnet://" not in body

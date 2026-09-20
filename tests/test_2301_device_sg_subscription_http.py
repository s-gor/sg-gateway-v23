from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from app.clients import sg_subscription_http_v4 as http
from app.security.auth import should_skip_auth


def _client():
    return SimpleNamespace(id=61, name="Device Client", enabled=True)


def _device():
    return SimpleNamespace(id=8, client_id=61, name="Планшет", enabled=True, is_primary=False)


def _app(monkeypatch) -> Flask:
    client = _client()
    device = _device()
    monkeypatch.setattr(http, "get_client_by_subscription_token", lambda token: client)
    monkeypatch.setattr(http, "get_client", lambda client_id: client if client_id == 61 else None)
    monkeypatch.setattr(http, "get_device", lambda device_id: device if device_id == 8 else None)
    monkeypatch.setattr(
        http,
        "build_sg_device_subscription_url",
        lambda item, access: f"https://vpn.example/sg/sub/v1/token/device/{access.id}",
    )
    document = {
        "format": "sg-subscription",
        "version": 1,
        "scope": "device",
        "client": {"id": 61, "name": "Device Client"},
        "summary": {"devices": 1, "profiles_assigned": 3, "profiles_ready": 3},
        "devices": [{"id": 8, "name": "Планшет", "primary": False, "profiles": []}],
    }
    monkeypatch.setattr(http, "build_sg_device_subscription_document", lambda item, device_id: document)
    monkeypatch.setattr(http, "build_compatible_device_subscription_body", lambda item, device_id: "ZGV2aWNlCg==")
    monkeypatch.setattr(http, "build_sg_device_subscription_text", lambda item, device_id: "# SG-SUBSCRIPTION/1\n# scope=device\n")
    monkeypatch.setattr(http, "build_qr_svg", lambda value: f"<svg>{value}</svg>")
    app = Flask(__name__)
    http.register_sg_subscription(app)
    return app


def test_device_subscription_exposes_universal_native_json_and_qr(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()

    default = client.get("/sg/sub/v1/token/device/8")
    native = client.get("/sg/sub/v1/token/device/8?format=sg")
    js = client.get("/sg/sub/v1/token/device/8?format=json")
    info = client.get("/api/clients/61/devices/8/sg-subscription-v1")
    qr_native = client.get("/clients/61/devices/8/sg-subscription-v1/qr")
    qr_universal = client.get("/clients/61/devices/8/sg-subscription-v1/qr/universal")

    assert default.status_code == 200
    assert default.get_data(as_text=True) == "ZGV2aWNlCg=="
    assert default.headers["X-SG-Subscription-Scope"] == "device"
    assert default.headers["X-SG-Subscription-Device"] == "8"
    assert native.get_data(as_text=True).startswith("# SG-SUBSCRIPTION/1")
    assert js.get_json()["scope"] == "device"

    payload = info.get_json()
    assert payload["universal_url"] == "https://vpn.example/sg/sub/v1/token/device/8"
    assert payload["native_url"].endswith("/device/8?format=sg")
    assert payload["json_url"].endswith("/device/8?format=json")

    assert b"/device/8?format=sg" in qr_native.data
    assert b"/device/8" in qr_universal.data
    assert b"?format=sg" not in qr_universal.data
    assert should_skip_auth(http.PUBLIC_DEVICE_ENDPOINT) is True


def test_device_subscription_rejects_device_from_another_client(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(http, "get_device", lambda device_id: SimpleNamespace(
        id=8,
        client_id=999,
        name="Other",
        enabled=True,
        is_primary=False,
    ))
    response = app.test_client().get("/sg/sub/v1/token/device/8")
    assert response.status_code == 404

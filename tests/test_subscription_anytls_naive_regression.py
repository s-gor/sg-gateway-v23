import base64
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from app.clients import exports, sg_subscription
from app.clients.repository import Client
from app.naiveproxy.integration import install as install_naiveproxy


def _client() -> Client:
    return Client(
        id=1,
        name="Regression",
        enabled=True,
        expires_at=None,
        awg_status="missing",
        xray_status="missing",
    )


def test_anytls_canonical_subscription_preserves_managed_transport_contract():
    source = (
        "anytls://secret@dc1.casacam.net:443"
        "?security=tls&sni=dc1.casacam.net&alpn=sg-anytls&fp=firefox&type=tcp"
        "#AnyTLS"
    )

    result = sg_subscription._canonical_uri("anytls", source)
    query = parse_qs(urlsplit(result).query)

    assert query["security"] == ["tls"]
    assert query["sni"] == ["dc1.casacam.net"]
    assert query["alpn"] == ["sg-anytls"]
    assert query["fp"] == ["firefox"]
    assert query["type"] == ["tcp"]


def test_sg_subscription_uses_live_naiveproxy_export_registration(monkeypatch):
    expected = "naive+https://user:pass@dc1.casacam.net:443#NaiveProxy"

    monkeypatch.setattr(exports, "protocol_ready", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        exports,
        "build_protocol_export",
        lambda *args, **kwargs: SimpleNamespace(
            body=expected,
            media_type="text/plain; charset=utf-8",
        ),
    )

    entry = sg_subscription._profile_entry(
        _client(),
        SimpleNamespace(id=11),
        ("naiveproxy", "naiveproxy", "naiveproxy", "NaiveProxy", "naiveproxy", "uri"),
    )

    assert entry["ready"] is True
    assert entry["uri"] == expected


def test_universal_subscription_includes_ready_naiveproxy(monkeypatch):
    install_naiveproxy()

    from app.engines import provisioning

    monkeypatch.setattr(
        exports,
        "is_export_ready",
        lambda client, engine, device=None: engine == "naiveproxy",
    )
    monkeypatch.setattr(exports, "tls_overview", lambda: {"https_ready": True})
    monkeypatch.setattr(
        exports,
        "_deployment_config",
        lambda client, engine, device=None: (
            {
                "username": "user",
                "password": "safe-password-with-very-long-value",
                "device_id": 11,
                "host": "dc1.casacam.net",
            }
            if engine == "naiveproxy"
            else {}
        ),
    )
    monkeypatch.setattr(
        provisioning,
        "get_connection_settings",
        lambda engine: SimpleNamespace(
            host="dc1.casacam.net",
            port=10447,
            config={"domain": "dc1.casacam.net"},
        ),
    )

    export = exports.build_subscription(_client(), SimpleNamespace(id=11, is_primary=True, name=""))
    decoded = base64.b64decode(export.body).decode("utf-8")

    assert (
        "naive+https://user:safe-password-with-very-long-value@dc1.casacam.net:443"
        in decoded
    )

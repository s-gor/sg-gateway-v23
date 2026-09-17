from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from app.clients import exports, sg_subscription
from app.clients.repository import Client


def _client() -> Client:
    return Client(
        id=1,
        name="Regression",
        enabled=True,
        expires_at=None,
        awg_status="missing",
        xray_status="missing",
    )


def test_anytls_canonical_subscription_preserves_managed_alpn():
    source = (
        "anytls://secret@dc1.casacam.net:443"
        "?security=tls&sni=dc1.casacam.net&alpn=sg-anytls&fp=firefox&type=tcp"
        "#AnyTLS"
    )

    result = sg_subscription._canonical_uri("anytls", source)
    query = parse_qs(urlsplit(result).query)

    assert query["sni"] == ["dc1.casacam.net"]
    assert query["alpn"] == ["sg-anytls"]


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

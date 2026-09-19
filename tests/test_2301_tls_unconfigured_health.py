from app.security import tls


def test_unconfigured_tls_is_not_a_health_warning(monkeypatch):
    monkeypatch.setattr(
        tls,
        "overview",
        lambda: {
            "domain": "",
            "https_ready": False,
            "certificate": {},
        },
    )

    result = tls.health_status()

    assert result["status"] == "ok"
    assert result["message"] == "Домен и HTTPS ещё не настроены"


def test_configured_but_not_ready_tls_still_requires_attention(monkeypatch):
    monkeypatch.setattr(
        tls,
        "overview",
        lambda: {
            "domain": "vpn.example.test",
            "https_ready": False,
            "certificate": {},
        },
    )

    result = tls.health_status()

    assert result["status"] == "warning"
    assert "ещё не готов" in result["message"]

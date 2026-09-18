from app.maintenance import health


def test_cached_health_refreshes_when_tls_state_file_changes(monkeypatch) -> None:
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 1.0, "value": "warning", "tls_state_mtime_ns": 10}
    )
    monkeypatch.setattr(health, "_tls_state_mtime_ns", lambda: 11)
    monkeypatch.setattr(
        health,
        "collect_health_checks",
        lambda: [health.HealthCheck("TLS", "ok", "ready")],
    )

    assert health.cached_health_summary() == "ok"
    assert health._HEALTH_SUMMARY_CACHE["tls_state_mtime_ns"] == 11


def test_cached_health_populates_on_first_non_system_page(monkeypatch) -> None:
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 0.0, "value": None, "tls_state_mtime_ns": None}
    )
    monkeypatch.setattr(
        health,
        "collect_health_checks",
        lambda: [health.HealthCheck("TLS", "ok", "ready")],
    )

    assert health.cached_health_summary() == "ok"
    assert health._HEALTH_SUMMARY_CACHE["value"] == "ok"

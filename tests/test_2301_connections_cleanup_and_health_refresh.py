from app.maintenance import health


def test_cached_health_never_starts_full_scan(monkeypatch) -> None:
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 0.0, "value": "ok", "tls_state_mtime_ns": None}
    )
    monkeypatch.setattr(
        health,
        "collect_health_checks",
        lambda: (_ for _ in ()).throw(
            AssertionError("ordinary page navigation must not run full health checks")
        ),
    )
    assert health.cached_health_summary() == "ok"


def test_cached_health_uses_default_when_cache_is_empty(monkeypatch) -> None:
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 0.0, "value": None, "tls_state_mtime_ns": None}
    )
    monkeypatch.setattr(
        health,
        "collect_health_checks",
        lambda: (_ for _ in ()).throw(
            AssertionError("ordinary page navigation must not populate health synchronously")
        ),
    )
    assert health.cached_health_summary() == "warning"

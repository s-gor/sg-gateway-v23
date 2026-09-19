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



def test_tls_refresh_runs_health_once_when_tls_state_changes(monkeypatch) -> None:
    calls = {"checks": 0}
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 0.0, "value": "warning", "tls_state_mtime_ns": 10}
    )
    monkeypatch.setattr(health, "_tls_state_mtime_ns", lambda: 11)

    def fake_checks():
        calls["checks"] += 1
        return [health.HealthCheck("TLS", "ok", "ready")]

    monkeypatch.setattr(health, "collect_health_checks", fake_checks)

    assert health.refresh_after_tls_change() == "ok"
    assert calls["checks"] == 1
    assert health._HEALTH_SUMMARY_CACHE["tls_state_mtime_ns"] == 11

    assert health.refresh_after_tls_change() == "ok"
    assert calls["checks"] == 1


def test_tls_refresh_is_not_part_of_cached_navigation(monkeypatch) -> None:
    health._HEALTH_SUMMARY_CACHE.update(
        {"updated_at": 0.0, "value": "ok", "tls_state_mtime_ns": 11}
    )
    monkeypatch.setattr(
        health,
        "refresh_after_tls_change",
        lambda: (_ for _ in ()).throw(
            AssertionError("ordinary navigation must not refresh TLS health")
        ),
    )
    assert health.cached_health_summary() == "ok"

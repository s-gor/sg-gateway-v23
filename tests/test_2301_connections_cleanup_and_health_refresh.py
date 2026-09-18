from pathlib import Path

from app.maintenance import health


ROOT = Path(__file__).resolve().parents[1]


def test_mihomo_connections_ui_is_port_free_and_pending_is_neutral() -> None:
    template = (ROOT / "app/web/templates/_mihomo_panel.html").read_text(encoding="utf-8")
    css = (ROOT / "app/web/static/sg-controls-final-v1.css").read_text(encoding="utf-8")

    assert "TCP или UDP" not in template
    assert "Ожидает применения" in template
    assert "Не применено" not in template
    assert "Три независимых listener двух движков." not in template
    assert "Ошибка дополнительного движка" not in template
    assert "Только для уже применённой конфигурации." not in template
    assert "#93672E" not in css
    assert ".sg-runtime-switch.state-pending .sg-runtime-copy strong { color: var(--sgc-muted) !important; }" in css


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

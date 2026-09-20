from types import SimpleNamespace


def test_system_context_collects_health_only_once(monkeypatch):
    import app.main as main

    calls = 0

    def fake_checks():
        nonlocal calls
        calls += 1
        return [SimpleNamespace(status="warning")]

    monkeypatch.setattr(main, "collect_health_checks", fake_checks)
    monkeypatch.setattr(main, "health_summary", lambda: (_ for _ in ()).throw(AssertionError("system context must derive summary from collected checks")))
    monkeypatch.setattr(main, "list_connections", lambda: [])
    monkeypatch.setattr(main, "_dashboard_resources", lambda: {})
    monkeypatch.setattr(main, "count_clients", lambda: 0)
    monkeypatch.setattr(main, "list_backups", lambda: [])
    monkeypatch.setattr(main, "get_release_manifest", lambda: {})
    monkeypatch.setattr(main, "get_version", lambda: "test")

    result = main._sg_gateway_system_context()

    assert calls == 1
    assert result["report"]["health"] == "warning"
    assert len(result["health_checks"]) == 1


def test_connection_health_reads_settings_in_one_batch(monkeypatch):
    from app.maintenance import health

    settings = {
        "amneziawg31": SimpleNamespace(
            host="awg31.example",
            port=587,
            config={"server_public_key": "real-key"},
        ),
        "xray": SimpleNamespace(
            host="xray.example",
            port=443,
            config={"public_key": "real-key", "short_id": "abcd", "server_name": "example.com"},
        ),
    }
    calls = 0

    def batch(engines):
        nonlocal calls
        calls += 1
        assert tuple(engines) == ("amneziawg31", "xray")
        return settings

    monkeypatch.setattr(health, "list_connection_settings", batch, raising=False)
    monkeypatch.setattr(
        health,
        "get_connection_settings",
        lambda *_: (_ for _ in ()).throw(AssertionError("health must not open settings DB per engine")),
        raising=False,
    )
    monkeypatch.setattr(
        health,
        "run_hostd_command",
        lambda command: SimpleNamespace(status="ok", message=f"{command}: ok"),
    )

    checks = health._connection_checks()

    assert calls == 1
    assert len(checks) == 2

def test_header_health_refreshes_real_summary_after_process_start(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SG_GATEWAY_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("SG_GATEWAY_SECRET_KEY", "health-header-secret")
    monkeypatch.setenv("SG_GATEWAY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SG_GATEWAY_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("SG_GATEWAY_PUBLIC_ADDRESS", "203.0.113.10")

    calls = 0

    def real_summary():
        nonlocal calls
        calls += 1
        return "ok"

    monkeypatch.setattr(main, "health_summary", real_summary)
    monkeypatch.setattr(
        main,
        "cached_health_summary",
        lambda: (_ for _ in ()).throw(AssertionError("fresh header must not use sticky default warning")),
    )

    app = main.create_app()
    processor = next(
        item for item in app.template_context_processors[None]
        if getattr(item, "__name__", "") == "inject_globals"
    )
    with app.test_request_context("/"):
        context = processor()

    assert calls == 1
    assert context["panel_health"] == "ok"


from types import SimpleNamespace

from app.db import init_db
import app.maintenance.health as health
from app.maintenance.health import collect_health_checks, health_summary


def test_health_checks_report_expected_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db()

    checks = collect_health_checks()
    names = {check.name for check in checks}

    assert "База данных" in names
    assert "Каталог резервных копий" in names
    assert "Настройки AmneziaWG 3.1" in names
    assert "Настройки AmneziaWG" not in names
    assert health_summary() in {"ok", "warning", "error"}


def test_awg_health_check_uses_awg31_only(monkeypatch):
    calls: list[tuple[str, object]] = []

    awg31 = SimpleNamespace(
        host="awg31.internal",
        port=587,
        config={"server_public_key": "real-awg31-key"},
    )
    xray = SimpleNamespace(
        host="example.test",
        port=443,
        config={
            "public_key": "real-xray-key",
            "short_id": "abcd1234",
            "server_name": "www.example.com",
        },
    )

    def fake_list_connection_settings(engines):
        requested = tuple(engines)
        calls.append(("settings", requested))
        assert requested == ("amneziawg31", "xray")
        return {"amneziawg31": awg31, "xray": xray}

    def fake_run_hostd_command(command: str):
        calls.append(("hostd", command))
        return SimpleNamespace(status="ok", message="ready")

    monkeypatch.setattr(health, "list_connection_settings", fake_list_connection_settings)
    monkeypatch.setattr(health, "run_hostd_command", fake_run_hostd_command)

    checks = health._connection_checks()
    assert calls[0] == ("settings", ("amneziawg31", "xray"))
    assert ("hostd", "awg31.status") in calls
    assert all("amneziawg3" not in str(call) and call != ("settings", ("amneziawg", "xray")) for call in calls)
    assert checks


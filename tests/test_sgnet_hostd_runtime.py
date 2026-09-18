from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sg_hostd import sgnet_runtime as runtime


def _settings(enabled=True):
    return SimpleNamespace(
        enabled=enabled,
        config={
            "server_name": "edge.example.com",
            "certificate_path": "/cert.pem",
            "private_key_path": "/key.pem",
        },
    )


def test_status_never_returns_device_secret(monkeypatch):
    monkeypatch.setattr(runtime, "get_connection_settings", lambda engine: _settings())
    monkeypatch.setattr(runtime, "_service_active", lambda service=runtime.DEFAULT_SERVICE: True)
    monkeypatch.setattr(
        runtime,
        "_health",
        lambda path=runtime.DEFAULT_HEALTH_SOCKET: {
            "runtime_version": "0.1.0",
            "protocol_version": 1,
            "active_sessions": 2,
            "active_streams": 5,
            "auth_failures": 0,
        },
    )
    payload = runtime.status()
    rendered = repr(payload)
    assert "secret" not in rendered.lower()
    assert "/key.pem" not in rendered
    assert payload["internal_listener"] == "127.0.0.1:10448"


def test_test_candidate_rejects_validation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "get_connection_settings", lambda engine: _settings())
    monkeypatch.setattr(runtime, "build_runtime_document", lambda: {"version": 1})
    monkeypatch.setattr(
        runtime,
        "_validate_candidate",
        lambda candidate, binary=runtime.DEFAULT_BINARY: (_ for _ in ()).throw(
            runtime.SgNetRuntimeError("invalid")
        ),
    )
    with pytest.raises(runtime.SgNetRuntimeError):
        runtime.test_candidate(candidate=tmp_path / "candidate.json")


def test_apply_restores_previous_config_after_restart_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_refresh_single_edge", lambda script=runtime.DEFAULT_EDGE_REFRESH: None)
    config_path = tmp_path / "sgnet.json"
    previous_path = tmp_path / "sgnet.json.previous"
    candidate = tmp_path / "sgnet.json.new"
    config_path.write_text('{"old":true}\n', encoding="utf-8")

    monkeypatch.setattr(runtime, "get_connection_settings", lambda engine: _settings())
    monkeypatch.setattr(runtime, "build_runtime_document", lambda: {"version": 1, "new": True})
    monkeypatch.setattr(runtime, "_validate_candidate", lambda candidate, binary=runtime.DEFAULT_BINARY: None)
    monkeypatch.setattr(runtime, "_service_active", lambda service=runtime.DEFAULT_SERVICE: True)

    calls = []
    def fake_run(command, timeout=30):
        calls.append(command)
        code = 1 if command[:2] == ["systemctl", "restart"] and len(calls) == 1 else 0
        return SimpleNamespace(returncode=code, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_run", fake_run)
    with pytest.raises(runtime.SgNetRuntimeError):
        runtime.apply(
            config_path=config_path,
            previous_path=previous_path,
            candidate_path=candidate,
            binary=tmp_path / "sgnet-server",
            service="sgnet-test.service",
            health_socket=tmp_path / "health.sock",
        )

    assert config_path.read_text(encoding="utf-8") == '{"old":true}\n'
    assert previous_path.read_text(encoding="utf-8") == '{"old":true}\n'


def test_disabled_apply_stops_service_without_writing_config(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_refresh_single_edge", lambda script=runtime.DEFAULT_EDGE_REFRESH: None)
    monkeypatch.setattr(runtime, "get_connection_settings", lambda engine: _settings(False))
    monkeypatch.setattr(runtime, "_service_active", lambda service=runtime.DEFAULT_SERVICE: False)
    commands = []
    monkeypatch.setattr(
        runtime,
        "_run",
        lambda command, timeout=30: (
            commands.append(command)
            or SimpleNamespace(returncode=0, stdout="", stderr="")
        ),
    )
    payload = runtime.apply(
        config_path=tmp_path / "sgnet.json",
        previous_path=tmp_path / "previous.json",
        candidate_path=tmp_path / "candidate.json",
        binary=tmp_path / "binary",
        service="sgnet-test.service",
        health_socket=tmp_path / "health.sock",
    )
    assert payload["enabled"] is False
    assert commands == [["systemctl", "stop", "sgnet-test.service"]]
    assert not (tmp_path / "sgnet.json").exists()

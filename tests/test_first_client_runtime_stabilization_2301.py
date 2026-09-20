from types import SimpleNamespace

import pytest

from app.clients import runtime


def _result(status="ok", message="ok", **payload):
    return SimpleNamespace(status=status, message=message, payload=payload)


def test_regular_apply_remains_single_pass(monkeypatch):
    calls = []

    def fake(command, timeout):
        calls.append((command, timeout))
        return _result(sequence=1)

    monkeypatch.setattr(runtime, "run_hostd_command", fake)
    result = runtime.apply_clients_runtime()

    assert calls == [("clients.apply", 300)]
    assert result["sequence"] == 1
    assert "stabilized" not in result


def test_fresh_client_create_requires_two_successful_applies(monkeypatch):
    calls = []

    def fake(command, timeout):
        calls.append((command, timeout))
        return _result(message=f"pass-{len(calls)}", sequence=len(calls))

    monkeypatch.setattr(runtime, "run_hostd_command", fake)
    result = runtime.apply_clients_runtime(stabilize=True)

    assert calls == [("clients.apply", 300), ("clients.apply", 300)]
    assert result["sequence"] == 2
    assert result["stabilized"] is True
    assert result["initial_message"] == "pass-1"


def test_second_stabilization_failure_is_not_reported_as_success(monkeypatch):
    calls = []

    def fake(command, timeout):
        calls.append((command, timeout))
        if len(calls) == 1:
            return _result(message="first-ok")
        return _result(status="error", message="second-failed")

    monkeypatch.setattr(runtime, "run_hostd_command", fake)

    with pytest.raises(runtime.ClientWorkflowError, match="second-failed"):
        runtime.apply_clients_runtime(stabilize=True)

    assert calls == [("clients.apply", 300), ("clients.apply", 300)]

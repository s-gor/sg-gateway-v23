from __future__ import annotations

from app.hostd.client import run_hostd_command


class ClientWorkflowError(RuntimeError):
    pass


def _apply_clients_once() -> dict:
    result = run_hostd_command("clients.apply", timeout=300)
    payload = dict(result.payload)
    payload.setdefault("message", result.message)
    payload.setdefault("ok", result.status == "ok")
    if result.status != "ok":
        raise ClientWorkflowError(
            result.message or "Не удалось применить клиентские конфигурации"
        )
    return payload


def apply_clients_runtime(*, stabilize: bool = False) -> dict:
    """Apply client runtime and optionally require a convergence pass.

    A freshly created client immediately after clean install may race with the
    runtime reload chain: the first full apply can return success before every
    live backend has settled on the new credentials.  Client creation therefore
    requires two consecutive successful full-catalogue applies.  Existing edit,
    manual apply and rollback flows keep the established single-apply behavior.
    """
    first = _apply_clients_once()
    if not stabilize:
        return first

    second = _apply_clients_once()
    second["stabilized"] = True
    second["initial_message"] = str(first.get("message") or "")
    return second

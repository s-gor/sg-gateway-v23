from __future__ import annotations

from flask import Flask, jsonify

from app.hostd.client import run_hostd_command

_ACTIONS = {
    "test": "sgnet.test",
    "apply": "sgnet.apply",
    "restart": "sgnet.restart",
    "rollback": "sgnet.rollback",
}


def _result_payload(result) -> dict:
    return {
        "ok": result.status == "ok",
        "status": result.status,
        "message": result.message,
        **dict(result.payload),
    }


def register_sgnet_http(app: Flask) -> None:
    if "sgnet_status_api" not in app.view_functions:
        def status():
            return jsonify(_result_payload(run_hostd_command("sgnet.status", timeout=30)))

        app.add_url_rule(
            "/api/sgnet/status",
            endpoint="sgnet_status_api",
            view_func=status,
            methods=["GET"],
        )

    for action, command in _ACTIONS.items():
        endpoint = f"sgnet_{action}_api"
        if endpoint in app.view_functions:
            continue

        def handler(command=command):
            result = run_hostd_command(command, timeout=120)
            payload = _result_payload(result)
            return jsonify(payload), (200 if payload["ok"] else 409)

        app.add_url_rule(
            f"/api/sgnet/{action}",
            endpoint=endpoint,
            view_func=handler,
            methods=["POST"],
        )

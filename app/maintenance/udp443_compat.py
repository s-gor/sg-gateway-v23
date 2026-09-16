from __future__ import annotations

import copy
from typing import Any

from app.connections.settings import get_connection_settings
from app.xray.salamander import (
    GECKO_MODE,
    SALAMANDER_MODE,
    SALAMANDER_MODE_NONE,
    SalamanderError,
    ensure_base_has_no_salamander,
    generate_password,
    normalise_mode,
    password_ready,
)
from app.xray.settings_transactions import (
    begin as begin_settings_transaction,
    pending as pending_settings_transaction,
    rollback as rollback_settings_transaction,
)


class Udp443CompatibilityError(RuntimeError):
    pass


def normalise_hysteria2_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    original = copy.deepcopy(dict(config or {}))
    candidate = copy.deepcopy(original)
    if not bool(candidate.get("hysteria2_enabled")):
        return candidate, False

    try:
        mode = normalise_mode(candidate.get("hysteria2_obfs_mode") or SALAMANDER_MODE_NONE)
    except SalamanderError:
        mode = SALAMANDER_MODE
    if mode == SALAMANDER_MODE_NONE:
        mode = SALAMANDER_MODE

    password = str(candidate.get("hysteria2_obfs_password") or "").strip()
    if not password_ready(password):
        password = generate_password()

    base = ensure_base_has_no_salamander(candidate.get("hysteria2_finalmask") or {})
    candidate.update(
        {
            "hysteria2_obfs_mode": mode,
            "hysteria2_obfs_password": password,
            "hysteria2_finalmask": base,
            "hysteria2_salamander_managed": True,
        }
    )
    return candidate, candidate != original


def migrate() -> dict[str, Any]:
    try:
        settings = get_connection_settings("xray")
    except KeyError:
        return {"changed": False, "mode": "absent"}
    candidate, changed = normalise_hysteria2_config(dict(settings.config))
    if not changed:
        return {"changed": False, "mode": str(candidate.get("hysteria2_obfs_mode") or "none")}

    transaction = begin_settings_transaction("xray", settings.host, int(settings.port), candidate)
    try:
        from sg_hostd.client_runtime import apply_xray_runtime

        result = apply_xray_runtime()
        if not bool(result.get("ok")):
            raise Udp443CompatibilityError(str(result.get("message") or "Xray compatibility apply failed"))
    except Exception:
        current = pending_settings_transaction("xray")
        if current is not None and current.id == transaction.id:
            rollback_settings_transaction(transaction.id, status="rolled_back_udp443_compat_error")
        raise

    applied = get_connection_settings("xray")
    applied_config = dict(applied.config)
    mode = normalise_mode(applied_config.get("hysteria2_obfs_mode") or SALAMANDER_MODE_NONE)
    if mode not in {SALAMANDER_MODE, GECKO_MODE} or not password_ready(applied_config.get("hysteria2_obfs_password")):
        raise Udp443CompatibilityError("Hysteria2 UDP/443 compatibility invariant was not persisted")
    return {"changed": True, "mode": mode}


def main() -> None:
    result = migrate()
    if result["changed"]:
        print(f"[SG-Gateway UDP443] Hysteria2 compatibility applied: {result['mode']}")
    else:
        print(f"[SG-Gateway UDP443] Hysteria2 compatibility already valid: {result['mode']}")


if __name__ == "__main__":
    main()

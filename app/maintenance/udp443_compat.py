from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path
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


NAIVEPROXY_INTERNAL_PORT = 10447
ANYTLS_TCP_INTERNAL_PORT = 10449


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


def _run_checked(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 180) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout or "").strip()
    raise Udp443CompatibilityError(
        detail or f"Single Edge migration command failed: {' '.join(command)}"
    )


def _ensure_naiveproxy_runtime(app_root: Path) -> bool:
    binary = app_root / "naiveproxy/bin/caddy"
    unit = Path("/etc/systemd/system/sg-gateway-naiveproxy.service")
    if binary.is_file() and os.access(binary, os.X_OK) and unit.is_file():
        return False

    installer = app_root / "deploy/install-naiveproxy.sh"
    if not installer.is_file():
        raise Udp443CompatibilityError(
            "NaiveProxy runtime is missing and install-naiveproxy.sh is unavailable"
        )
    env = os.environ.copy()
    env["SG_GATEWAY_SOURCE_ROOT"] = str(app_root)
    env.setdefault("SG_GATEWAY_UPDATE_BRANCH", os.environ.get("SG_GATEWAY_GITHUB_BRANCH", ""))
    _run_checked(["bash", str(installer)], env=env, timeout=300)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise Udp443CompatibilityError("NaiveProxy runtime repair did not install caddy")
    return True


def migrate_single_edge_tcp_runtime() -> dict[str, Any]:
    """Migrate live TLS backends before the updater transaction is committed.

    The updater calls this module at Stage 9, after the pre-migration integrity
    checks but before UPDATE_FINISHED. NaiveProxy and Nginx live under paths
    covered by the Safety Backup. sing-box is applied last; its own apply path
    restores the previous config/service if that operation fails.
    """
    if os.geteuid() != 0:
        return {"changed": False, "mode": "skipped-non-root"}

    from app.naiveproxy.integration import install as install_naiveproxy
    from app.security.tls import overview as tls_overview

    tls = tls_overview()
    domain = str(tls.get("domain") or "").strip().lower().rstrip(".")
    if not bool(tls.get("https_ready")) or not domain:
        return {"changed": False, "mode": "https-not-ready"}

    app_root = Path(os.environ.get("SG_GATEWAY_APP_ROOT") or "/opt/sg-gateway")
    access = app_root / "deploy/configure-panel-access.sh"
    if not access.is_file():
        raise Udp443CompatibilityError("Single Edge Nginx refresh helper is unavailable")

    runtime_repaired = _ensure_naiveproxy_runtime(app_root)
    install_naiveproxy()

    from app.connections.settings import update_connection_settings
    from sg_hostd.naiveproxy_runtime import sync as sync_naiveproxy

    current = get_connection_settings("naiveproxy")
    config = dict(current.config)
    certificate = str(tls.get("certificate_path") or f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    private_key = f"/etc/letsencrypt/live/{domain}/privkey.pem"
    config.update(
        {
            "domain": domain,
            "certificate_path": certificate,
            "private_key_path": private_key,
        }
    )
    if not update_connection_settings("naiveproxy", domain, NAIVEPROXY_INTERNAL_PORT, config):
        raise Udp443CompatibilityError("NaiveProxy Single Edge settings update failed")

    naive = sync_naiveproxy()
    if not bool(naive.get("ok", True)):
        raise Udp443CompatibilityError(
            str(naive.get("message") or "NaiveProxy Single Edge runtime apply failed")
        )

    # Replace a syntactically-valid legacy stream config too. Stage 7 repairs
    # only invalid Nginx, so without this unconditional refresh old servers can
    # keep routing 443 without the AnyTLS ALPN branch forever.
    _run_checked([str(access), "--mode", "stream-refresh"], timeout=120)

    # Apply sing-box last. There are no fallible live mutations after this
    # point, so a successful AnyTLS migration cannot be stranded outside the
    # updater's rollback coverage by a later Nginx/Naive failure.
    from sg_hostd.client_runtime import _apply_singbox

    singbox = _apply_singbox()
    failed = [item for item in singbox if not item.ok]
    if failed:
        raise Udp443CompatibilityError(
            "; ".join(item.message for item in failed)
        )

    return {
        "changed": True,
        "mode": "single-edge-tcp",
        "naiveproxy_port": NAIVEPROXY_INTERNAL_PORT,
        "anytls_port": ANYTLS_TCP_INTERNAL_PORT,
        "naiveproxy_runtime_repaired": runtime_repaired,
    }


def main() -> None:
    result = migrate()
    if result["changed"]:
        print(f"[SG-Gateway UDP443] Hysteria2 compatibility applied: {result['mode']}")
    else:
        print(f"[SG-Gateway UDP443] Hysteria2 compatibility already valid: {result['mode']}")

    tcp = migrate_single_edge_tcp_runtime()
    if tcp["changed"]:
        print(
            "[SG-Gateway TCP443] Single Edge runtime migrated: "
            f"NaiveProxy={tcp['naiveproxy_port']}, AnyTLS={tcp['anytls_port']}"
        )
    else:
        print(f"[SG-Gateway TCP443] Single Edge runtime unchanged: {tcp['mode']}")


if __name__ == "__main__":
    main()

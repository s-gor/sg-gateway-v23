from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests/test_2301_single_edge_tls_hub.py"
ACCESS = ROOT / "deploy/configure-panel-access.sh"
UPDATER = ROOT / "deploy/update-from-github-core.sh"
WORKFLOW = ROOT / ".github/workflows/fix-nginx-refresh-selfheal.yml"
SELF = Path(__file__).resolve()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"patch anchor not found: {label}")
    return text.replace(old, new, 1)


def append_red_test() -> None:
    body = TEST.read_text(encoding="utf-8")
    marker = "def test_refresh_uses_explicit_domain_and_updater_self_heals_managed_stream_config():"
    if marker in body:
        return
    body += r'''


def test_refresh_uses_explicit_domain_and_updater_self_heals_managed_stream_config():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")

    assert 'write_stream_config(){ local default_backend="$1" domain="$2";' in access
    assert '$domain 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;' in access

    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$HOST"' in configure

    refresh = access[access.index("refresh_https(){"):access.index("refresh_stream_config(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"' in refresh

    assert 'refresh_stream_config(){' in access
    stream_refresh = access[access.index("refresh_stream_config(){"):access.index("renew_https(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"' in stream_refresh
    assert "bootstrap_tls_edge" not in stream_refresh
    assert "apply_client_runtime" not in stream_refresh
    assert 'stream-refresh) refresh_stream_config' in access

    assert "NGINX_REPAIRED=0" in updater
    assert "repair_managed_nginx_if_needed()" in updater
    assert '"$PREFIX/deploy/configure-panel-access.sh" --mode stream-refresh' in updater
    assert 'if (( NGINX_REPAIRED == 1 )); then' in updater
    assert "[%s/10]" in updater
    assert 'run_stage 7 "Repair managed Nginx Single Edge config if needed" repair_managed_nginx_if_needed' in updater
    assert 'run_stage 8 "Проверка HTTPS, credentials, Nginx и runtime" verify_final' in updater
    assert 'run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration' in updater
    assert 'run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service' in updater
'''
    TEST.write_text(body, encoding="utf-8")


def prove_red() -> None:
    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_2301_single_edge_tls_hub.py",
            "-k",
            "refresh_uses_explicit_domain_and_updater_self_heals_managed_stream_config",
        ],
        cwd=ROOT,
        text=True,
    )
    if result.returncode == 0:
        raise SystemExit("expected RED regression did not fail")
    print("RED confirmed")


def patch_access() -> None:
    text = ACCESS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "usage(){ printf '%s\\n' 'configure-panel-access.sh --mode https --host panel.example.com --port 63443' 'configure-panel-access.sh --mode renew|rollback|refresh'; }",
        "usage(){ printf '%s\\n' 'configure-panel-access.sh --mode https --host panel.example.com --port 63443' 'configure-panel-access.sh --mode renew|rollback|refresh|stream-refresh'; }",
        "usage",
    )
    text = replace_once(
        text,
        '[[ "$MODE" =~ ^(https|renew|rollback|refresh)$ ]] || { usage; exit 1; }',
        '[[ "$MODE" =~ ^(https|renew|rollback|refresh|stream-refresh)$ ]] || { usage; exit 1; }',
        "mode regex",
    )
    text = replace_once(
        text,
        'write_stream_config(){ local default_backend="$1"; cat > "$STREAM_CONF" <<EOF',
        'write_stream_config(){ local default_backend="$1" domain="$2"; [[ -n "$domain" ]] || fail "не задан домен для stream routing"; cat > "$STREAM_CONF" <<EOF',
        "write_stream_config signature",
    )
    text = replace_once(
        text,
        '    $HOST 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;',
        '    $domain 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;',
        "stream domain",
    )
    text = replace_once(
        text,
        'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT"; write_https_site "$HOST"',
        'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$HOST"; write_https_site "$HOST"',
        "configure explicit host",
    )
    text = replace_once(
        text,
        'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT"; write_https_site "$domain"',
        'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"; write_https_site "$domain"',
        "refresh explicit domain",
    )
    text = replace_once(
        text,
        'renew_https(){ local domain="$(read_state_value domain)";',
        'refresh_stream_config(){ local domain; domain="$(read_state_value domain)"; [[ -n "$domain" ]] || fail "HTTPS ещё не настроен"; ensure_stream_include; write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"; nginx -t; systemctl reload nginx.service; log "Single Edge stream-конфигурация обновлена"; }\nrenew_https(){ local domain="$(read_state_value domain)";',
        "stream refresh helper",
    )
    text = replace_once(
        text,
        'case "$MODE" in https) configure_https;; renew) renew_https;; rollback) rollback_https;; refresh) refresh_https;; esac',
        'case "$MODE" in https) configure_https;; renew) renew_https;; rollback) rollback_https;; refresh) refresh_https;; stream-refresh) refresh_stream_config;; esac',
        "stream refresh dispatch",
    )
    ACCESS.write_text(text, encoding="utf-8")


def patch_updater() -> None:
    text = UPDATER.read_text(encoding="utf-8")
    text = replace_once(text, 'ASSETS_RECOVERY_SOURCE=""\n', 'ASSETS_RECOVERY_SOURCE=""\nNGINX_REPAIRED=0\n', "repair flag")
    text = replace_once(
        text,
        "printf '%s[SG-Gateway Update] [%s/7]%s %s\\n'",
        "printf '%s[SG-Gateway Update] [%s/10]%s %s\\n'",
        "stage total",
    )
    text = replace_once(
        text,
        'verify_final() {\n',
        '''repair_managed_nginx_if_needed() {
  if nginx -t >/dev/null 2>&1; then
    return 0
  fi

  local state
  state="$(https_state)"
  eval "$state"
  [[ "${HTTPS_READY:-0}" == "1" && -n "${HTTPS_DOMAIN:-}" ]] || \\
    fail "Nginx on-disk config is invalid and HTTPS state is unavailable for managed repair"
  [[ -x "$PREFIX/deploy/configure-panel-access.sh" ]] || \\
    fail "managed Nginx repair helper is unavailable"

  printf '[SG-Gateway Update] Existing managed Nginx config is invalid; rebuilding Single Edge stream routing.\\n'
  "$PREFIX/deploy/configure-panel-access.sh" --mode stream-refresh
  nginx -t >/dev/null
  NGINX_REPAIRED=1
}

verify_final() {
''',
        "repair function",
    )
    text = replace_once(
        text,
        '''  before="$(cat "$BACKUP_DIR/nginx-before.sha256")"
  after="$(fingerprint_paths \\
    "$NGINX_CONFIG" \\
    "$NGINX_SITE_AVAILABLE" \\
    "$NGINX_SITE_ENABLED" \\
    "$NGINX_STREAM_CONFIG")"
  [[ "$before" == "$after" ]] || fail "Nginx configuration changed during Update"
''',
        '''  before="$(cat "$BACKUP_DIR/nginx-before.sha256")"
  after="$(fingerprint_paths \\
    "$NGINX_CONFIG" \\
    "$NGINX_SITE_AVAILABLE" \\
    "$NGINX_SITE_ENABLED" \\
    "$NGINX_STREAM_CONFIG")"
  if (( NGINX_REPAIRED == 1 )); then
    [[ "$before" != "$after" ]] || fail "managed Nginx repair did not change the invalid configuration"
  else
    [[ "$before" == "$after" ]] || fail "Nginx configuration changed during Update"
  fi
''',
        "verify repaired nginx",
    )
    text = replace_once(
        text,
        '''  run_stage 6 "AWG31 Stage3A migration внутри Update transaction" run_stage3a_migration
  run_stage 7 "Проверка HTTPS, credentials, Nginx и runtime" verify_final
  run_stage 8 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration
  run_stage 9 "UDP/443 edge service rollout" ensure_udp_edge_service
''',
        '''  run_stage 6 "AWG31 Stage3A migration внутри Update transaction" run_stage3a_migration
  run_stage 7 "Repair managed Nginx Single Edge config if needed" repair_managed_nginx_if_needed
  run_stage 8 "Проверка HTTPS, credentials, Nginx и runtime" verify_final
  run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration
  run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service
''',
        "stage ordering",
    )
    UPDATER.write_text(text, encoding="utf-8")


def rebuild_integrity() -> None:
    WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    files = sorted(
        rel
        for rel in tracked
        if rel != "SOURCE-SHA256SUMS"
        and not rel.startswith(".github/workflows/")
        and rel != "tools/_tmp_fix_nginx_refresh_selfheal.py"
    )
    rows = [f"{hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()}  {rel}\n" for rel in files]
    (ROOT / "SOURCE-SHA256SUMS").write_text("".join(rows), encoding="utf-8")
    print(f"source integrity rebuilt: {len(rows)} files")


def main() -> None:
    append_red_test()
    prove_red()
    patch_access()
    patch_updater()
    subprocess.run(["bash", "-n", str(ACCESS)], check=True, cwd=ROOT)
    subprocess.run(["bash", "-n", str(UPDATER)], check=True, cwd=ROOT)
    rebuild_integrity()


if __name__ == "__main__":
    main()

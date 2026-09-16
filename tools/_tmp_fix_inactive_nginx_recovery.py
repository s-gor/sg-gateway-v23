from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


updater_path = Path("deploy/update-from-github-core.sh")
updater = updater_path.read_text(encoding="utf-8")
updater = replace_once(
    updater,
    'NGINX_REPAIRED=0\n',
    'NGINX_REPAIRED=0\nNGINX_PREUPDATE_ACTIVE=0\n',
    "nginx pre-update state global",
)
updater = replace_once(
    updater,
    '  for command in curl tar gzip python3 sha256sum systemctl du df find sort; do\n',
    '  for command in curl tar gzip python3 sha256sum systemctl nginx du df find sort; do\n',
    "preflight nginx command",
)
old_preflight = '''  systemctl is-active --quiet nginx.service || fail "nginx.service is not active before update"
  systemctl is-active --quiet "$HOSTD_SERVICE" || fail "$HOSTD_SERVICE is not active before update"
  systemctl is-active --quiet "$PANEL_SERVICE" || fail "$PANEL_SERVICE is not active before update"

  local old_version
  old_version="$(tr -d '\\r\\n' < "$PREFIX/VERSION")"
  printf '[SG-Gateway Update] Installed VERSION: %s\\n' "$old_version"

  local state
  state="$(https_state)"
  eval "$state"
  if [[ "${HTTPS_READY:-0}" == "1" ]]; then
    printf '[SG-Gateway Update] HTTPS: %s:%s\\n' "$HTTPS_DOMAIN" "$PANEL_PORT"
    curl --noproxy '*' -fsS --max-time 12 \\
      --resolve "${HTTPS_DOMAIN}:${PANEL_PORT}:127.0.0.1" \\
      "https://${HTTPS_DOMAIN}:${PANEL_PORT}/health" >/dev/null
  else
    printf '[SG-Gateway Update] HTTPS: not configured; IP/HTTP mode will be preserved.\\n'
  fi
'''
new_preflight = '''  NGINX_PREUPDATE_ACTIVE=0
  systemctl is-active --quiet nginx.service && NGINX_PREUPDATE_ACTIVE=1 || true
  systemctl is-active --quiet "$HOSTD_SERVICE" || fail "$HOSTD_SERVICE is not active before update"
  systemctl is-active --quiet "$PANEL_SERVICE" || fail "$PANEL_SERVICE is not active before update"

  local old_version
  old_version="$(tr -d '\\r\\n' < "$PREFIX/VERSION")"
  printf '[SG-Gateway Update] Installed VERSION: %s\\n' "$old_version"

  local state
  state="$(https_state)"
  eval "$state"

  if (( NGINX_PREUPDATE_ACTIVE == 0 )); then
    if nginx -t >/dev/null 2>&1; then
      fail "nginx.service is not active before update"
    fi
    [[ "${HTTPS_READY:-0}" == "1" && -n "${HTTPS_DOMAIN:-}" && -f "$NGINX_STREAM_CONFIG" ]] || \\
      fail "nginx.service is inactive with invalid config and managed HTTPS state is unavailable for repair"
    printf '[SG-Gateway Update] Nginx is inactive with invalid managed config; managed Nginx repair will run after Safety Backup.\\n'
  fi

  if [[ "${HTTPS_READY:-0}" == "1" ]]; then
    printf '[SG-Gateway Update] HTTPS: %s:%s\\n' "$HTTPS_DOMAIN" "$PANEL_PORT"
    if (( NGINX_PREUPDATE_ACTIVE == 1 )); then
      curl --noproxy '*' -fsS --max-time 12 \\
        --resolve "${HTTPS_DOMAIN}:${PANEL_PORT}:127.0.0.1" \\
        "https://${HTTPS_DOMAIN}:${PANEL_PORT}/health" >/dev/null
    else
      printf '[SG-Gateway Update] HTTPS health check deferred until managed Nginx repair.\\n'
    fi
  else
    printf '[SG-Gateway Update] HTTPS: not configured; IP/HTTP mode will be preserved.\\n'
  fi
'''
updater = replace_once(updater, old_preflight, new_preflight, "preflight inactive nginx recovery")
old_states = '''    case "$service" in
      "$PANEL_SERVICE"|"$HOSTD_SERVICE"|"$AWG31_SERVICE") continue ;;
    esac
'''
new_states = '''    case "$service" in
      "$PANEL_SERVICE"|"$HOSTD_SERVICE"|"$AWG31_SERVICE") continue ;;
      "nginx.service")
        if (( NGINX_REPAIRED == 1 )); then
          continue
        fi
        ;;
    esac
'''
updater = replace_once(updater, old_states, new_states, "nginx repaired service-state allowance")
old_success = "  printf '[SG-Gateway Update] TLS certificates/Nginx/AWG3 runtime/VPN cores were not modified.\\n'\n"
new_success = '''  if (( NGINX_REPAIRED == 1 )); then
    printf '[SG-Gateway Update] TLS certificates/AWG3 runtime/VPN cores were not modified; managed Nginx stream config was repaired.\\n'
  else
    printf '[SG-Gateway Update] TLS certificates/Nginx/AWG3 runtime/VPN cores were not modified.\\n'
  fi
'''
updater = replace_once(updater, old_success, new_success, "accurate success message")
updater_path.write_text(updater, encoding="utf-8")

access_path = Path("deploy/configure-panel-access.sh")
access = access_path.read_text(encoding="utf-8")
old_refresh = 'refresh_stream_config(){ local domain; domain="$(read_state_value domain)"; [[ -n "$domain" ]] || fail "HTTPS ещё не настроен"; ensure_stream_include; write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"; nginx -t; systemctl reload nginx.service; log "Single Edge stream-конфигурация обновлена"; }'
new_refresh = 'refresh_stream_config(){ local domain; domain="$(read_state_value domain)"; [[ -n "$domain" ]] || fail "HTTPS ещё не настроен"; ensure_stream_include; write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain"; nginx -t; if systemctl is-active --quiet nginx.service; then systemctl reload nginx.service; else systemctl start nginx.service; fi; log "Single Edge stream-конфигурация обновлена"; }'
access = replace_once(access, old_refresh, new_refresh, "stream refresh starts inactive nginx")
access_path.write_text(access, encoding="utf-8")

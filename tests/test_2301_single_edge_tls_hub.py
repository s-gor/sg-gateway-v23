from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_tls_hub_uses_placeholder_not_panel_gateway():
    app_runtime = (ROOT / "app/naiveproxy/runtime.py").read_text(encoding="utf-8")
    hostd_runtime = (ROOT / "hostd/sg_hostd/naiveproxy_runtime.py").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")

    assert "https://{current.domain}:{current.port}" in app_runtime
    assert "bind 127.0.0.1" in app_runtime
    assert "reverse_proxy @sg_xhttp_tls h2c://127.0.0.1:{XHTTP_TLS_INTERNAL_PORT}" in app_runtime
    assert "reverse_proxy http://127.0.0.1:{PLACEHOLDER_HTTP_INTERNAL_PORT}" in app_runtime
    assert "PANEL_GATEWAY_PORT" not in app_runtime

    assert "https://{settings['domain']}:{settings['port']}" in hostd_runtime
    assert "bind 127.0.0.1" in hostd_runtime
    assert "reverse_proxy @sg_xhttp_tls h2c://127.0.0.1:{XHTTP_TLS_INTERNAL_PORT}" in hostd_runtime
    assert "reverse_proxy http://127.0.0.1:{PLACEHOLDER_HTTP_INTERNAL_PORT}" in hostd_runtime
    assert "PANEL_GATEWAY_PORT" not in hostd_runtime

    assert "$HOST 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;" in access
    assert 'PLACEHOLDER_HTTP_INTERNAL_PORT="10446"' in access
    assert "PANEL_HTTP_INTERNAL_PORT" not in access
    assert "listen 127.0.0.1:$PLACEHOLDER_HTTP_INTERNAL_PORT;" in access
    assert "listen $PUBLIC_PORT ssl;" in access
    assert "listen [::]:$PUBLIC_PORT ssl;" in access
    assert "SG_GATEWAY_FULL_BACKUP_UPLOAD_FIX1" in access
    assert "SG_GATEWAY_02111_RESTORE_RESTART_PAGE_FIX" in access
    assert "client_max_body_size 0;" in access
    assert "$cookie_security_directive" in access


def test_panel_https_is_separate_from_shared_443():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'CONFIGURED_PUBLIC_PORT="$(get_env "$ENV_FILE" SG_GATEWAY_PUBLIC_PORT 63443)"' in access
    assert 'case "$PUBLIC_PORT" in 22|80|443|' in access
    assert '"https://$domain:$PUBLIC_PORT/health"' in access
    assert 'log "Панель HTTPS $PUBLIC_PORT: OK"' in access
    assert 'log "Панель: https://$HOST:$PUBLIC_PORT/"' in access
    assert 'log "Заглушка: http://$HOST/ и https://$HOST/"' in access


def test_https_bootstraps_shared_tls_edge_before_verification():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert "bootstrap_tls_edge(){" in access
    assert "from sg_hostd.naiveproxy_runtime import sync" in access
    assert 'update_connection_settings("naiveproxy", domain, 10447, config)' in access
    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    assert 'bootstrap_tls_edge "$HOST" "$cert_file" "$key_file"' in configure
    assert configure.index('bootstrap_tls_edge "$HOST" "$cert_file" "$key_file"') < configure.index('verify_https_contract "$HOST"')


def test_internal_placeholder_tls_listener_has_certificate_directives():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    marker = "listen 127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT ssl;"
    start = access.index(marker)
    end = access.index("\nserver {", start + len(marker))
    block = access[start:end]
    assert "ssl_certificate $cert;" in block
    assert "ssl_certificate_key $key;" in block

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

    assert "$domain 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;" in access
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


def test_tcp_443_edge_routes_anytls_by_alpn_and_mieru_as_non_tls():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")

    assert 'ANYTLS_ALPN="sg-anytls"' in installer
    assert 'map \\$ssl_preread_server_name \\$sg_gateway_sni_backend {' in installer
    assert 'map \\$ssl_preread_protocol \\$sg_gateway_protocol_backend {' in installer
    assert '"" 127.0.0.1:${MIHOMO_PORT};' in installer
    assert 'default \\$sg_gateway_sni_backend;' in installer
    assert 'map \\$ssl_preread_alpn_protocols \\$sg_gateway_443_backend {' in installer
    assert '~\\b${ANYTLS_ALPN}\\b 127.0.0.1:${ANYTLS_PORT};' in installer
    assert 'default \\$sg_gateway_protocol_backend;' in installer

    assert 'MIERU_TCP_INTERNAL_PORT="10448"' in access
    assert 'ANYTLS_TCP_INTERNAL_PORT="10449"' in access
    assert 'ANYTLS_ALPN="sg-anytls"' in access
    assert 'map \\$ssl_preread_server_name \\$sg_gateway_sni_backend {' in access
    assert 'map \\$ssl_preread_protocol \\$sg_gateway_protocol_backend {' in access
    assert '"" 127.0.0.1:$MIERU_TCP_INTERNAL_PORT;' in access
    assert 'default \\$sg_gateway_sni_backend;' in access
    assert 'map \\$ssl_preread_alpn_protocols \\$sg_gateway_443_backend {' in access
    assert '~\\b$ANYTLS_ALPN\\b 127.0.0.1:$ANYTLS_TCP_INTERNAL_PORT;' in access
    assert 'default \\$sg_gateway_protocol_backend;' in access


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
    assert "[%s/11]" in updater
    assert 'run_stage 7 "Repair managed Nginx Single Edge config if needed" repair_managed_nginx_if_needed' in updater
    assert 'run_stage 8 "Проверка HTTPS, credentials, Nginx и runtime" verify_final' in updater
    assert 'run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration' in updater
    assert 'run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service' in updater
    assert 'run_stage 11 "TCP/443 AnyTLS/NaiveProxy runtime migration" migrate_single_edge_tcp_runtime' in updater


def test_update_migrates_existing_anytls_and_naiveproxy_before_finishing():
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")

    assert "migrate_single_edge_tcp_runtime()" in updater
    start = updater.index("migrate_single_edge_tcp_runtime()")
    end = updater.index("\nbind_panel_update_state()", start)
    migration = updater[start:end]

    assert "repair_naiveproxy_runtime_if_needed" in migration
    assert "apply_split_mihomo_singbox_runtime" in migration
    assert 'update_connection_settings("naiveproxy", domain, 10447, config)' in migration
    assert "sync_naiveproxy" in migration
    assert '"$PREFIX/deploy/configure-panel-access.sh" --mode stream-refresh' in migration
    assert "127.0.0.1:10447" in migration
    assert "127.0.0.1:10449" in migration

    stage10 = updater.index('run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service')
    stage11 = updater.index('run_stage 11 "TCP/443 AnyTLS/NaiveProxy runtime migration" migrate_single_edge_tcp_runtime')
    finish = updater.index("bind_panel_update_state")
    assert stage10 < stage11 < finish

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_tls_hub_uses_placeholder_not_panel_gateway():
    app_runtime = (ROOT / "app/naiveproxy/runtime.py").read_text(encoding="utf-8")
    hostd_runtime = (ROOT / "hostd/sg_hostd/naiveproxy_runtime.py").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")

    assert ":{current.port}, {current.domain}:{current.port}" in app_runtime
    assert "bind 127.0.0.1" in app_runtime
    assert "reverse_proxy @sg_xhttp_tls h2c://127.0.0.1:{XHTTP_TLS_INTERNAL_PORT}" in app_runtime
    assert "reverse_proxy http://127.0.0.1:{PLACEHOLDER_HTTP_INTERNAL_PORT}" in app_runtime
    assert "PANEL_GATEWAY_PORT" not in app_runtime

    assert ":{settings['port']}, {settings['domain']}:{settings['port']}" in hostd_runtime
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


def test_panel_https_stays_on_dedicated_63443_not_tcp443():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    verify = access[access.index("verify_https_contract(){"):access.index("# SG_GATEWAY_02111_XRAY_FULL_ACCESS_POLICY")]
    assert 'PANEL_HOST="$HOST"' in configure
    assert 'log "Панель: https://$HOST:$PUBLIC_PORT/"' in configure
    assert 'wait_panel_contract "$domain" "$PUBLIC_PORT"' in verify
    assert 'fail "панель не должна публиковаться через TCP 443"' in verify


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

    assert 'write_stream_config(){' in access
    assert '$domain 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;' in access
    assert '$panel_domain 127.0.0.1:$PANEL_TLS_INTERNAL_PORT;' not in access

    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$HOST" "$PANEL_HOST"' in configure

    refresh = access[access.index("refresh_https(){"):access.index("refresh_stream_config(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain" "$panel_domain"' in refresh

    assert 'refresh_stream_config(){' in access
    stream_refresh = access[access.index("refresh_stream_config(){"):access.index("renew_https(){")]
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$domain" "$panel_domain"' in stream_refresh
    assert "bootstrap_tls_edge" not in stream_refresh
    assert "apply_client_runtime" not in stream_refresh
    assert 'stream-refresh) refresh_stream_config' in access

    assert "NGINX_REPAIRED=0" in updater
    assert "refresh_managed_nginx()" in updater
    assert '"$PREFIX/deploy/configure-panel-access.sh" --mode nginx-refresh' in updater
    assert 'if (( NGINX_REPAIRED == 0 )); then' in updater
    assert "[%s/10]" in updater
    assert 'run_stage 7 "Обновление managed Nginx HTTPS/Single Edge" refresh_managed_nginx' in updater
    assert 'run_stage 8 "Проверка HTTPS, credentials, Nginx и runtime" verify_final' in updater
    assert 'run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration' in updater
    assert 'run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service' in updater


def test_transactional_stage9_migrates_existing_anytls_and_naiveproxy_tcp_edge():
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    compat = (ROOT / "app/maintenance/udp443_compat.py").read_text(encoding="utf-8")

    assert "NAIVEPROXY_INTERNAL_PORT = 10447" in compat
    assert "ANYTLS_TCP_INTERNAL_PORT = 10449" in compat
    assert "migrate_single_edge_tcp_runtime" in compat
    assert "_apply_singbox" in compat
    assert 'update_connection_settings("naiveproxy", domain, NAIVEPROXY_INTERNAL_PORT, config)' in compat
    assert "sync_naiveproxy" in compat
    assert "stream-refresh" in compat

    start = compat.index("def migrate_single_edge_tcp_runtime")
    end = compat.index("\ndef main", start)
    migration = compat[start:end]
    assert migration.index("sync_naiveproxy") < migration.index("stream-refresh") < migration.index("_apply_singbox")

    verify = updater.index('run_stage 8 "Проверка HTTPS, credentials, Nginx и runtime" verify_final')
    stage9 = updater.index('run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration" run_udp443_compat_migration')
    stage10 = updater.index('run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service')
    finish = updater.index("\n  UPDATE_FINISHED=1\n", stage10)
    assert verify < stage9 < stage10 < finish


def test_tls_bootstrap_loads_installed_runtime_environment():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    bootstrap = access[access.index("bootstrap_tls_edge(){"):access.index("detect_public_ipv4(){")]
    assert '"$ENV_FILE" "$RUNTIME_ENV" /etc/sg-gateway/engine-secrets.env' in bootstrap
    assert 'os.environ[name] = value' in bootstrap
    assert "from app.connections.settings import get_connection_settings" in bootstrap
    assert bootstrap.index("os.environ[name] = value") < bootstrap.index("from app.connections.settings import get_connection_settings")


def test_certificate_activation_avoids_mid_transaction_hooks_and_stale_tls_sessions():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    refresh = access[access.index("refresh_https(){"):access.index("refresh_stream_config(){")]
    renew = access[access.index("renew_https(){"):access.index("rollback_https(){")]
    assert configure.count("--no-directory-hooks") >= 2
    assert "systemctl restart nginx.service" in configure
    assert "systemctl restart nginx.service" in refresh
    assert "--no-directory-hooks" in renew
    assert "apply_client_runtime" not in renew

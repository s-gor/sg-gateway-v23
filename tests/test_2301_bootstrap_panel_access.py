from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_install_keeps_dedicated_panel_port():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'DEFAULT_PANEL_PORT="63443"' in installer
    assert 'listen ${PANEL_PORT};' in installer
    assert '"80/tcp" "${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in installer


def test_security_ui_uses_one_domain_only():
    template = (ROOT / "app/web/templates/security.html").read_text(encoding="utf-8")
    tls = (ROOT / "app/security/tls.py").read_text(encoding="utf-8")
    assert 'name="panel_domain"' not in template
    assert "Домен SG-Gateway" in template
    assert "порт 63443" in template
    assert "normalized_panel_domain = normalized_domain" in tls


def test_https_panel_is_on_63443_and_not_routed_through_tcp443():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    verify = access[access.index("verify_https_contract(){"):access.index("# SG_GATEWAY_02111_XRAY_FULL_ACCESS_POLICY")]
    assert 'PANEL_HOST="$HOST"' in configure
    assert 'write_stream_config "127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT" "$HOST" "$PANEL_HOST"' in configure
    assert 'wait_panel_contract "$domain" "$PUBLIC_PORT"' in verify
    assert 'fail "панель не должна публиковаться через TCP 443"' in verify
    assert 'log "Панель: https://$HOST:$PUBLIC_PORT/"' in configure


def test_http_redirects_to_https_panel_port_and_acme_stays_reachable():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_backend(){")]
    assert 'location / { return 308 https://$domain:$PUBLIC_PORT\\$request_uri; }' in https_site
    assert 'location ^~ /.well-known/acme-challenge/' in https_site
    verify = access[access.index("verify_https_contract(){"):access.index("# SG_GATEWAY_02111_XRAY_FULL_ACCESS_POLICY")]
    assert 'wait_http_redirect_contract "$domain" "$domain" "$PUBLIC_PORT"' in verify


def test_protocol_domain_443_remains_placeholder_only():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_backend(){")]
    assert 'listen 127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT ssl;' in https_site
    placeholder = https_site[https_site.index('listen 127.0.0.1:$PLACEHOLDER_TLS_INTERNAL_PORT ssl;'):]
    placeholder = placeholder[:placeholder.index("\nserver {", 1)]
    assert 'location / { return 404; }' in placeholder
    assert "proxy_pass http://127.0.0.1:$BACKEND_PORT;" not in placeholder


def test_update_migrates_legacy_panel_domain_back_to_main_domain():
    core = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert "panel_domain = domain" in core
    assert "panel_edge_443 = False" in core
    assert '"$PREFIX/deploy/configure-panel-access.sh" --mode nginx-refresh' in core
    refresh = access[access.index("refresh_nginx_https(){"):access.index("refresh_stream_config(){")]
    assert 'panel_domain="$domain"' in refresh
    assert 'write_state "$domain" "$domain" refresh' in refresh


def test_https_transition_does_not_mutate_firewall():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert "ufw allow" not in access
    assert "ufw --force delete" not in access


def test_full_uninstall_removes_installer_firewall_rules_it_created():
    uninstall = (ROOT / "deploy/full-uninstall-ubuntu.sh").read_text(encoding="utf-8")
    assert 'PANEL_PORT="63443"' in uninstall
    assert '"${PANEL_PORT}/tcp"' in uninstall

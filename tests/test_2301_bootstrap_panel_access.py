from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_install_keeps_63443_bootstrap_panel_contract():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'DEFAULT_PANEL_PORT="63443"' in installer
    assert 'listen ${PANEL_PORT};' in installer
    assert '"80/tcp" "${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in installer
    assert "http://%s:%s" in installer
    assert '"$PUBLIC_ADDRESS" "$PANEL_PORT"' in installer


def test_separate_panel_domain_turns_63443_into_redirect_only_listener():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_backend(){")]
    assert 'if [[ "$panel_domain" != "$domain" ]]' in https_site
    assert 'return 308 https://$panel_domain\\$request_uri;' in https_site
    redirect_part = https_site.split('if [[ "$panel_domain" != "$domain" ]]', 1)[1].split('else', 1)[0]
    assert 'proxy_pass http://127.0.0.1:$BACKEND_PORT;' not in redirect_part
    assert 'PANEL_TLS_INTERNAL_PORT="7445"' in access
    assert '$panel_domain 127.0.0.1:$PANEL_TLS_INTERNAL_PORT;' in access


def test_https_contract_verifies_legacy_redirect_to_panel_443():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'wait_bootstrap_redirect_contract(){' in access
    verify = access[access.index("verify_https_contract(){"):access.index("xray_full_access(){")]
    assert 'wait_bootstrap_redirect_contract "$domain" "$panel_domain"' in verify
    assert '308|https://$panel_domain/security' in access


def test_https_transition_does_not_mutate_firewall():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'ufw allow' not in access
    assert 'ufw --force delete' not in access


def test_full_uninstall_still_removes_installer_firewall_rules_it_created():
    uninstall = (ROOT / "deploy/full-uninstall-ubuntu.sh").read_text(encoding="utf-8")
    assert 'PANEL_PORT="63443"' in uninstall
    assert '"${PANEL_PORT}/tcp"' in uninstall


def test_http_hosts_redirect_to_matching_https_and_keep_acme_reachable():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_backend(){")]
    assert 'server_name $domain _;' in https_site
    assert 'location / { return 308 https://$domain\\$request_uri; }' in https_site
    assert 'server_name $panel_domain;' in https_site
    assert 'location / { return 308 https://$panel_domain\\$request_uri; }' in https_site
    assert https_site.count('location ^~ /.well-known/acme-challenge/') >= 2


def test_https_contract_verifies_both_http_redirects():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'wait_http_redirect_contract(){' in access
    verify = access[access.index("verify_https_contract(){"):access.index("xray_full_access(){")]
    assert 'wait_http_redirect_contract "$domain" "$domain"' in verify
    assert 'wait_http_redirect_contract "$panel_domain" "$panel_domain"' in verify


def test_update_applies_current_managed_https_routing_without_runtime_rebuild():
    core = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'run_stage 7 "Обновление managed Nginx HTTPS/Single Edge" refresh_managed_nginx' in core
    assert '"$PREFIX/deploy/configure-panel-access.sh" --mode nginx-refresh' in core
    assert 'nginx-refresh) refresh_nginx_https' in access
    nginx_refresh = access[access.index("refresh_nginx_https(){"):access.index("refresh_stream_config(){")]
    assert "write_https_site" in nginx_refresh
    assert "write_stream_config" in nginx_refresh
    assert "bootstrap_tls_edge" not in nginx_refresh
    assert "apply_client_runtime" not in nginx_refresh


def test_update_verifies_panel_domain_on_443_after_managed_refresh():
    core = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    assert '("PANEL_DOMAIN", panel_domain)' in core
    assert '("PANEL_EDGE_443", "1" if panel_edge_443 else "0")' in core
    assert '--resolve "${PANEL_DOMAIN}:443:127.0.0.1"' in core


def test_protocol_domain_placeholder_redirects_stale_panel_paths_to_panel_host():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_backend(){")]
    assert https_site.count('return 308 https://$panel_domain\\$request_uri;') >= 3
    assert 'location = / { try_files /index.html =404;' in https_site
    assert 'location = /index.html { try_files /index.html =404;' in https_site


def test_panel_domain_recovery_prefers_state_then_request_then_certificate_san():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'REQUEST_FILE="$STATE_DIR/tls-request.json"' in access
    assert 'read_effective_panel_domain(){' in access
    assert 'payload.get("panel_domain")' in access
    assert 'DNS:([^,\\s]+)' in access
    refresh = access[access.index("refresh_nginx_https(){"):access.index("refresh_stream_config(){")]
    assert 'panel_domain="$(read_effective_panel_domain "$domain")"' in refresh


def test_updater_recovers_panel_domain_from_tls_request():
    core = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    assert '"$DATA_DIR/security/tls-request.json"' in core
    assert 'request_payload.get("panel_domain")' in core
    assert 'panel_edge_443 = bool(panel_domain and panel_domain != domain)' in core

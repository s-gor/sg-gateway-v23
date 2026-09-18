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

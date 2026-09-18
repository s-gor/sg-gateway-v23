from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_install_keeps_63443_bootstrap_panel_contract():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'DEFAULT_PANEL_PORT="63443"' in installer
    assert 'listen ${PANEL_PORT};' in installer
    assert '"80/tcp" "${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in installer
    assert "http://%s:%s" in installer
    assert '"$PUBLIC_ADDRESS" "$PANEL_PORT"' in installer


def test_separate_panel_domain_retires_public_bootstrap_listener_without_firewall_changes():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_placeholder_contract(){")]
    assert 'if [[ "$panel_domain" == "$domain" ]]' in https_site
    assert 'listen $PUBLIC_PORT ssl;' in https_site
    assert '$bootstrap_listener' in https_site
    assert 'PANEL_TLS_INTERNAL_PORT="7445"' in access
    assert '$panel_domain 127.0.0.1:$PANEL_TLS_INTERNAL_PORT;' in access
    assert 'ufw allow' not in access
    assert 'ufw --force delete' not in access


def test_https_activation_and_rollback_are_nginx_only_for_bootstrap_port():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    configure = access[access.index("configure_https(){"):access.index("refresh_https(){")]
    refresh = access[access.index("refresh_https(){"):access.index("refresh_stream_config(){")]
    rollback = access[access.index("rollback_https(){"):access.index('case "$MODE" in')]
    assert 'set_bootstrap_port_access' not in access
    assert 'systemctl restart nginx.service' in configure
    assert 'systemctl restart nginx.service' in refresh
    assert 'systemctl restart nginx.service' in rollback


def test_full_uninstall_still_removes_installer_firewall_rules_it_created():
    uninstall = (ROOT / "deploy/full-uninstall-ubuntu.sh").read_text(encoding="utf-8")
    assert 'PANEL_PORT="63443"' in uninstall
    assert '"${PANEL_PORT}/tcp"' in uninstall

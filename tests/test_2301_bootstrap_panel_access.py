from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_install_keeps_63443_bootstrap_panel_contract():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'DEFAULT_PANEL_PORT="63443"' in installer
    assert 'listen ${PANEL_PORT};' in installer
    assert '"80/tcp" "${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in installer
    assert "http://%s:%s" in installer
    assert '"$PUBLIC_ADDRESS" "$PANEL_PORT"' in installer


def test_https_activation_keeps_bootstrap_panel_listener():
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    https_site = access[access.index("write_https_site(){"):access.index("wait_placeholder_contract(){")]
    assert 'listen $PUBLIC_PORT ssl;' in https_site
    assert 'proxy_pass http://127.0.0.1:$BACKEND_PORT;' in https_site
    assert 'PANEL_TLS_INTERNAL_PORT="7445"' in access
    assert '$panel_domain 127.0.0.1:$PANEL_TLS_INTERNAL_PORT;' in access

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_tls_hub_uses_internal_nginx_panel_gateway():
    app_runtime = (ROOT / "app/naiveproxy/runtime.py").read_text(encoding="utf-8")
    hostd_runtime = (ROOT / "hostd/sg_hostd/naiveproxy_runtime.py").read_text(encoding="utf-8")
    access = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert "127.0.0.1:{current.port}" in app_runtime
    assert "reverse_proxy @sg_xhttp_tls h2c://127.0.0.1:{XHTTP_TLS_INTERNAL_PORT}" in app_runtime
    assert "reverse_proxy http://127.0.0.1:{PANEL_GATEWAY_PORT}" in app_runtime
    assert "127.0.0.1:{settings['port']}" in hostd_runtime
    assert "reverse_proxy @sg_xhttp_tls h2c://127.0.0.1:{XHTTP_TLS_INTERNAL_PORT}" in hostd_runtime
    assert "reverse_proxy http://127.0.0.1:{PANEL_GATEWAY_PORT}" in hostd_runtime
    assert "$HOST 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;" in access
    assert 'PANEL_HTTP_INTERNAL_PORT="10446"' in access
    assert "listen 127.0.0.1:$PANEL_HTTP_INTERNAL_PORT;" in access
    assert "listen $PUBLIC_PORT ssl;" not in access
    assert "SG_GATEWAY_FULL_BACKUP_UPLOAD_FIX1" in access
    assert "SG_GATEWAY_02111_RESTORE_RESTART_PAGE_FIX" in access
    assert "client_max_body_size 0;" in access
    assert "$cookie_security_directive" in access

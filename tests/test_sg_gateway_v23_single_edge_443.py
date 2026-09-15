from pathlib import Path

from app.naiveproxy.runtime import NaiveProxySettings, NaiveProxyUser, build_client_uri, render_caddyfile
from app.xray.profiles import _values

ROOT = Path(__file__).resolve().parents[1]


def test_xray_tcp_profiles_have_private_unique_backends_and_public_443():
    values = _values({}, 443)
    assert values["reality_tcp_port"] == 10443
    assert values["xhttp_reality_port"] == 10444
    assert values["xhttp_tls_port"] == 10445
    assert values["hysteria2_port"] == 8446


def test_xray_runtime_binds_migrated_tcp_inbounds_to_loopback():
    text = (ROOT / "hostd/sg_hostd/client_runtime.py").read_text(encoding="utf-8")
    assert 'tcp_listen = "127.0.0.1"' in text
    assert '"listen": tcp_listen' in text
    assert 'public_listen = "::"' in text


def test_installer_owns_one_public_tcp_443_edge_and_no_secondary_tcp_ingress():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'XHTTP_REALITY_PORT="10444"' in text
    assert 'XHTTP_TLS_PORT="10445"' in text
    assert 'NAIVEPROXY_INTERNAL_PORT="10447"' in text
    assert text.count('listen 443 reuseport;') == 1
    assert 'default 127.0.0.1:${REALITY_INTERNAL_PORT};' in text
    assert '8444/tcp' not in text
    assert '8445/tcp' not in text
    assert '9443/tcp' not in text


def test_awg31_uses_udp_443_independently_of_tcp_edge():
    text = (ROOT / "app/connections/awg31.py").read_text(encoding="utf-8")
    assert 'PORT = 443' in text or 'DEFAULT_PORT = 443' in text


def test_naiveproxy_backend_is_loopback_and_export_is_public_443():
    settings = NaiveProxySettings(domain="edge.example.com", port=10447)
    user = NaiveProxyUser(username="sg-user", password="0123456789abcdef")
    caddy = render_caddyfile(settings, [user])
    assert "127.0.0.1:10447" in caddy
    assert ":10447," not in caddy
    uri = build_client_uri(settings, user, public_port=443)
    assert "@edge.example.com:443" in uri
    assert ":10447" not in uri


def test_single_edge_router_has_deterministic_sni_routes_and_reality_fallback():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert '$ssl_preread_server_name' in text
    assert 'SG_GATEWAY_XHTTP_REALITY_SNI' in text
    assert 'SG_GATEWAY_TLS_EDGE_SNI' in text
    assert 'ssl_preread on;' in text

from pathlib import Path

from app.naiveproxy.runtime import NaiveProxySettings, NaiveProxyUser, build_client_uri, render_caddyfile
from app.xray.profiles import _values

ROOT = Path(__file__).resolve().parents[1]


def test_xray_tcp_profiles_have_private_unique_backends_and_public_443():
    values = _values({}, 443)
    assert values["reality_tcp_port"] == 10443
    assert values["xhttp_reality_port"] == 10444
    assert values["xhttp_tls_port"] == 10445
    assert values["hysteria2_port"] == 443


def test_xray_runtime_binds_all_single_edge_tcp_backends_to_loopback():
    text = (ROOT / "hostd/sg_hostd/client_runtime.py").read_text(encoding="utf-8")
    reality = text.split('if "reality_tcp" in enabled_profiles:', 1)[1].split('if "xhttp_reality" in enabled_profiles:', 1)[0]
    xhttp_reality = text.split('if "xhttp_reality" in enabled_profiles:', 1)[1].split('tls_needed =', 1)[0]
    xhttp_tls = text.split('if "xhttp_tls" in enabled_profiles:', 1)[1].split('if "hysteria2" in enabled_profiles:', 1)[0]
    assert 'port=profile.port' in reality
    assert 'listen="127.0.0.1"' in reality
    assert 'listen="127.0.0.1"' in xhttp_reality
    assert '"listen": "127.0.0.1"' in xhttp_tls
    assert 'listen=public_listen' not in xhttp_reality
    assert '"listen": tcp_listen' not in xhttp_tls
    assert 'public_listen = "::"' in text


def test_xhttp_reality_uses_router_sni_contract_end_to_end():
    runtime = (ROOT / "hostd/sg_hostd/client_runtime.py").read_text(encoding="utf-8")
    exports = (ROOT / "app/clients/exports.py").read_text(encoding="utf-8")
    assert "dest=XHTTP_REALITY_DEFAULT_TARGET" in runtime
    assert "server_name=XHTTP_REALITY_DEFAULT_SNI" in runtime
    assert "server_name=XHTTP_REALITY_DEFAULT_SNI" in exports
    assert "PUBLIC_TCP_PORT" in exports
    assert "XHTTP_REALITY_DEFAULT_SNI" in exports


def test_installer_owns_one_public_tcp_443_edge_and_no_secondary_tcp_ingress():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'XHTTP_REALITY_PORT="10444"' in text
    assert 'XHTTP_TLS_PORT="10445"' in text
    assert 'NAIVEPROXY_INTERNAL_PORT="10447"' in text
    assert text.count('listen 443 reuseport;') == 1
    assert 'default 127.0.0.1:${REALITY_INTERNAL_PORT};' in text
    assert '"${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in text
    assert '8444/tcp' not in text
    assert '8445/tcp' not in text
    assert '9443/tcp' not in text


def test_awg31_uses_udp_443_independently_of_tcp_edge():
    connection = (ROOT / "app/connections/awg31.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "app/clients/awg31_lifecycle.py").read_text(encoding="utf-8")
    runtime = (ROOT / "hostd/sg_hostd/awg31_runtime.py").read_text(encoding="utf-8")
    stage3a_common = (ROOT / "app/maintenance/awg31_stage3a_common.py").read_text(encoding="utf-8")
    stage3a_data = (ROOT / "app/maintenance/awg31_stage3a_data.py").read_text(encoding="utf-8")
    assert 'PORT = 443' in connection or 'DEFAULT_PORT = 443' in connection
    assert 'ENDPOINT = "awg31.internal:443"' in lifecycle
    assert 'ENDPOINT = "awg31.internal:443"' in stage3a_common
    assert 'AWG31_UDP_INTERNAL_PORT' in runtime
    assert 'f"ListenPort = {AWG31_UDP_INTERNAL_PORT}"' in runtime
    assert 'AWG31_UDP_INTERNAL_PORT' in stage3a_data
    assert 'f"ListenPort = {AWG31_UDP_INTERNAL_PORT}"' in stage3a_data
    assert "port = 443" in stage3a_data
    for text in (lifecycle, runtime, stage3a_common, stage3a_data):
        assert 'awg31.internal:587' not in text
        assert 'ListenPort = 587' not in text
    assert "port = 587" not in stage3a_data


def test_naiveproxy_backend_is_loopback_and_export_is_public_443():
    settings = NaiveProxySettings(domain="edge.example.com", port=10447)
    user = NaiveProxyUser(username="sg-user", password="0123456789abcdef")
    caddy = render_caddyfile(settings, [user])
    assert "https://edge.example.com:10447" in caddy
    assert "bind 127.0.0.1" in caddy
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

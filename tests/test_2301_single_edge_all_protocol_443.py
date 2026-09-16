from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_single_edge_defines_public_and_private_protocol_ports():
    text = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")
    assert "PUBLIC_TCP_PORT = 443" in text
    assert "PUBLIC_UDP_PORT = 443" in text
    assert "AWG31_UDP_INTERNAL_PORT" in text
    assert "HYSTERIA2_UDP_INTERNAL_PORT" in text
    assert "TUIC_UDP_INTERNAL_PORT" in text
    assert "MIERU_TCP_INTERNAL_PORT" in text
    assert "ANYTLS_TCP_INTERNAL_PORT" in text


def test_xray_hysteria_is_private_and_public_export_is_443():
    runtime = (ROOT / "hostd/sg_hostd/client_runtime.py").read_text(encoding="utf-8")
    exports = (ROOT / "app/clients/exports.py").read_text(encoding="utf-8")
    assert "HYSTERIA2_UDP_INTERNAL_PORT" in runtime
    assert '"listen": "127.0.0.1"' in runtime
    assert '"reality_tcp", "xhttp_reality", "xhttp_tls", "hysteria2"' in exports


def test_split_mihomo_backends_are_private():
    runtime = (ROOT / "hostd/sg_hostd/client_runtime.py").read_text(encoding="utf-8")
    assert "ANYTLS_TCP_INTERNAL_PORT" in runtime
    assert "TUIC_UDP_INTERNAL_PORT" in runtime
    assert '"listen": "127.0.0.1"' in runtime
    assert '"listen": "::"' not in runtime[runtime.index("def _apply_singbox"):runtime.index("def apply_split_mihomo_singbox_runtime")]


def test_mieru_single_edge_is_tcp_only():
    service = (ROOT / "app/mihomo/service.py").read_text(encoding="utf-8")
    template = (ROOT / "app/web/templates/_mihomo_panel.html").read_text(encoding="utf-8")
    assert '"mieru_transport": "TCP"' in service
    assert 'name="mieru_transport"' not in template


def test_all_non_xray_exports_use_public_443_constants():
    exports = (ROOT / "app/clients/exports.py").read_text(encoding="utf-8")
    assert "PUBLIC_UDP_PORT" in exports
    assert "build_mieru_link" in exports and "PUBLIC_TCP_PORT" in exports
    assert "build_anytls_link" in exports and "PUBLIC_TCP_PORT" in exports
    assert "build_tuic_link" in exports and "PUBLIC_UDP_PORT" in exports


def test_udp_edge_is_managed_service_and_only_public_udp_owner():
    assert (ROOT / "app/udp_edge/__init__.py").is_file()
    assert (ROOT / "app/udp_edge/classifier.py").is_file()
    assert (ROOT / "app/udp_edge/server.py").is_file()
    assert (ROOT / "deploy/sg-gateway-udp-edge.service").is_file()
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "sg-gateway-udp-edge.service" in installer
    assert '"443/udp"' in installer
    for legacy in ('"8446/udp"', '"10443/udp"', '"2099/udp"'):
        assert legacy not in installer

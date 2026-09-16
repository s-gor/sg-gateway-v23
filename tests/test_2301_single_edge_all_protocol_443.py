from pathlib import Path
from types import SimpleNamespace


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
    hysteria = exports[exports.index('elif profile_id == "hysteria2":'):exports.index('\n    else:\n        body = ""', exports.index('elif profile_id == "hysteria2":'))]
    assert "endpoint = format_host_port(host, public_profile_port)" in hysteria
    assert "endpoint = format_host_port(host, profile.port)" not in hysteria


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


def test_awg31_server_runtime_binds_private_udp_backend_only():
    data = (ROOT / "app/maintenance/awg31_stage3a_data.py").read_text(encoding="utf-8")
    runtime = (ROOT / "hostd/sg_hostd/awg31_runtime.py").read_text(encoding="utf-8")
    for source in (data, runtime):
        assert "AWG31_UDP_INTERNAL_PORT" in source
        assert 'f"ListenPort = {AWG31_UDP_INTERNAL_PORT}"' in source
        assert '"ListenPort = 443"' not in source


def test_udp_edge_is_managed_service_and_only_public_udp_owner():
    assert (ROOT / "app/udp_edge/__init__.py").is_file()
    assert (ROOT / "app/udp_edge/classifier.py").is_file()
    assert (ROOT / "app/udp_edge/server.py").is_file()
    assert (ROOT / "deploy/sg-gateway-udp-edge.service").is_file()
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "sg-gateway-udp-edge.service" in installer
    assert '"443/udp"' in installer
    assert '"${PANEL_PORT}/tcp" "443/tcp" "443/udp"' in installer
    assert 'systemctl enable --now "$UDP_EDGE_SERVICE"' in installer
    assert "sg-gateway-awg31.service sg-gateway-singbox.service sg-gateway-naiveproxy.service sg-gateway-udp-edge.service; do" in installer
    for legacy in ('"8446/udp"', '"10443/udp"', '"2099/udp"'):
        assert legacy not in installer


def test_hysteria2_single_edge_forces_managed_salamander(monkeypatch):
    import app.xray.profiles as profiles

    current_config = {
        "fingerprint": "firefox",
        "reality_tcp_enabled": True,
        "xhttp_reality_enabled": False,
        "xhttp_tls_enabled": False,
        "hysteria2_enabled": True,
        "hysteria2_port": 443,
        "hysteria2_obfs_mode": "none",
        "hysteria2_obfs_password": "",
        "hysteria2_finalmask": {},
        "hysteria2_uri_scheme": "hysteria2",
    }
    settings = SimpleNamespace(host="vpn.example", port=443, config=current_config)
    monkeypatch.setattr(
        profiles,
        "_config",
        lambda: (settings, dict(current_config), {"https_ready": True}),
    )
    monkeypatch.setattr(profiles, "_installed_xray_version", lambda: "26.9.9")

    prepared = profiles._prepare(
        {
            "host": "vpn.example",
            "fingerprint": "firefox",
            "reality_tcp_enabled": "on",
            "xhttp_reality_path": "/sg-xhttp-reality",
            "xhttp_reality_mode": "stream-one",
            "xhttp_tls_path": "/sg-xhttp-tls",
            "xhttp_tls_mode": "auto",
            "hysteria2_enabled": "on",
            "hysteria2_obfs_mode": "none",
        }
    )

    assert prepared.config["hysteria2_obfs_mode"] == profiles.SALAMANDER_MODE
    assert profiles.password_ready(prepared.config["hysteria2_obfs_password"])
    assert prepared.config["hysteria2_salamander_managed"] is True


def test_update_transaction_migrates_existing_plain_hysteria_before_finish():
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    assert "app.maintenance.udp443_compat" in updater
    assert "run_udp443_compat_migration" in updater
    assert "XRAY_CONFIG" in updater
    migration = updater.index('run_stage 8 "UDP/443 Hysteria2/TUIC compatibility migration"')
    finish = updater.index("UPDATE_FINISHED=1")
    assert migration < finish

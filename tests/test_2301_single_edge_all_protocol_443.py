from pathlib import Path

from app.xray import profiles

ROOT = Path(__file__).resolve().parents[1]


def test_single_edge_all_client_facing_ports_are_443():
    single_edge = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")
    exports = (ROOT / "app/clients/exports.py").read_text(encoding="utf-8")
    access = (ROOT / "app/clients/access.py").read_text(encoding="utf-8")
    awg31 = (ROOT / "app/connections/awg31.py").read_text(encoding="utf-8")
    mihomo = (ROOT / "app/mihomo/service.py").read_text(encoding="utf-8")

    assert "PUBLIC_TCP_PORT = 443" in single_edge
    assert "PUBLIC_UDP_PORT = 443" in single_edge
    assert "AWG31_UDP_PORT = PUBLIC_UDP_PORT" in single_edge
    assert "HYSTERIA2_DEFAULT_PORT = PUBLIC_UDP_PORT" in single_edge
    assert '"port": PUBLIC_TCP_PORT' in exports
    assert "public_port=PUBLIC_TCP_PORT" in access
    assert "public_port=PUBLIC_UDP_PORT" in access
    assert "AWG31_UDP_PORT" in awg31
    assert "PUBLIC_TCP_PORT" in mihomo


def test_udp_dispatcher_owns_public_443_and_private_backends():
    classifier = (ROOT / "app/udp_edge/classifier.py").read_text(encoding="utf-8")
    server = (ROOT / "app/udp_edge/server.py").read_text(encoding="utf-8")
    single_edge = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")

    assert "AWG31_UDP_INTERNAL_PORT = 10451" in single_edge
    assert "HYSTERIA2_UDP_INTERNAL_PORT = 10452" in single_edge
    assert "TUIC_UDP_INTERNAL_PORT = 10453" in single_edge
    assert "PUBLIC_UDP_PORT" in server
    assert "0.0.0.0" in server
    assert "::" in server
    assert "AWG31_UDP_INTERNAL_PORT" in classifier
    assert "HYSTERIA2_UDP_INTERNAL_PORT" in classifier
    assert "TUIC_UDP_INTERNAL_PORT" in classifier


def test_retired_awg2_awg3_not_client_facing():
    exports = (ROOT / "app/clients/exports.py").read_text(encoding="utf-8")
    assert '"amneziawg"' not in exports
    assert '"amneziawg3"' not in exports


def test_xhttp_reality_defaults_stay_separate_from_public_port():
    single_edge = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")
    assert 'XHTTP_REALITY_DEFAULT_SNI = "www.cloudflare.com"' in single_edge
    assert 'XHTTP_REALITY_DEFAULT_TARGET = "www.cloudflare.com:443"' in single_edge


def test_anytls_has_distinct_alpn_marker():
    single_edge = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")
    assert 'ANYTLS_ALPN = "sg-anytls"' in single_edge


def test_hysteria2_single_edge_forces_managed_salamander():
    prepared = profiles._prepare(
        {
            "xhttp_reality_enabled": False,
            "xhttp_tls_enabled": False,
            "hysteria2_enabled": True,
            "hysteria2_obfs_mode": "none",
            "hysteria2_obfs_password": "",
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
    migration = updater.index('run_stage 9 "UDP/443 Hysteria2/TUIC compatibility migration"')
    finish = updater.index("UPDATE_FINISHED=1")
    assert migration < finish

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def test_clean_install_quarantines_dead_sg_infosec_nginx_reference():
    body = INSTALLER.read_text(encoding="utf-8")

    assert "cleanup_stale_sg_infosec_nginx" in body
    assert "/etc/sg-infosec/web/tls.crt" in body
    assert "SG_GATEWAY_STALE_SG_INFOSEC_NGINX_FIX1" in body
    assert 'if (( UPDATE_MODE == 0 )); then' in body
    assert 'cleanup_stale_sg_infosec_nginx' in body

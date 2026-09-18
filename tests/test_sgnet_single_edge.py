from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sgnet_reserves_only_internal_loopback_backend():
    source = (ROOT / "app/single_edge.py").read_text(encoding="utf-8")
    assert "SGNET_INTERNAL_PORT = 10448" in source
    script = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'SGNET_INTERNAL_PORT="10448"' in script
    assert '$SGNET_SNI 127.0.0.1:$SGNET_INTERNAL_PORT;' in script
    assert "listen 10448" not in script
    assert "listen 443 reuseport;" in script


def test_sgnet_single_edge_mapping_is_conditional_and_has_no_custom_alpn():
    script = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert 'if [[ -n "$SGNET_SNI" ]]' in script
    assert 'SELECT enabled, config_json FROM connection_settings WHERE engine=\'sgnet\'' in script
    assert 'sgnet_line="    $SGNET_SNI 127.0.0.1:$SGNET_INTERNAL_PORT;"' in script
    assert "ssl_preread on;" in script
    lowered = script.lower()
    assert "alpn sg-net" not in lowered
    assert "alpn sgnet" not in lowered


def test_existing_single_edge_routes_remain_present():
    script = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert '$REALITY_SNI 127.0.0.1:$XRAY_INTERNAL_PORT;' in script
    assert '$XHTTP_REALITY_SNI 127.0.0.1:$XHTTP_REALITY_INTERNAL_PORT;' in script
    assert '$HOST 127.0.0.1:$TLS_EDGE_INTERNAL_PORT;' in script
    assert "default $default_backend;" in script


def test_protocol_identifying_sni_is_rejected():
    script = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8")
    assert '"$SGNET_SNI" != *sgnet*' in script
    assert '"$SGNET_SNI" != *sg-net*' in script

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_update_installs_enables_and_verifies_udp_edge_service_before_finish():
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")

    assert 'UDP_EDGE_SERVICE="sg-gateway-udp-edge.service"' in updater
    assert 'UDP_EDGE_UNIT="$(system_path /etc/systemd/system/sg-gateway-udp-edge.service)"' in updater
    assert '"$UDP_EDGE_UNIT"' in updater
    assert 'install -m 0644 "$PREFIX/deploy/sg-gateway-udp-edge.service" "$UDP_EDGE_UNIT"' in updater
    assert 'systemctl enable --now "$UDP_EDGE_SERVICE"' in updater
    assert 'cmp -s "$PREFIX/deploy/sg-gateway-udp-edge.service" "$UDP_EDGE_UNIT"' in updater

    rollout = updater.index('run_stage 10 "UDP/443 edge service rollout" ensure_udp_edge_service')
    finish = updater.index("UPDATE_FINISHED=1")
    assert rollout < finish


def test_update_rollback_tracks_udp_edge_service_state():
    updater = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")

    capture = updater[updater.index("capture_service_states()") : updater.index("verify_runtime_states_unchanged()")]
    assert '"$UDP_EDGE_SERVICE"' in capture

    rollback = updater[updater.index("rollback_update()") : updater.index("on_error()")]
    assert '"$UDP_EDGE_SERVICE"' in rollback


def test_udp_edge_unit_uses_persistent_writable_gateway_data_dir():
    unit = (ROOT / "deploy/sg-gateway-udp-edge.service").read_text(encoding="utf-8")

    assert "ProtectSystem=strict" in unit
    assert "Environment=SG_GATEWAY_DATA_DIR=/var/lib/sg-gateway" in unit
    assert "ReadWritePaths=/var/lib/sg-gateway" in unit
    assert "Environment=SG_GATEWAY_DATA_DIR=data" not in unit

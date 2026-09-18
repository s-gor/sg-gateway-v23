from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sgnet_systemd_unit_is_unprivileged_and_hardened():
    unit = (ROOT / "deploy/sg-gateway-sgnet.service").read_text(encoding="utf-8")
    assert "User=sg-gateway" in unit
    assert "Group=sg-gateway" in unit
    assert "ExecStart=/usr/local/bin/sgnet-server --config /etc/sg-gateway/sgnet.json" in unit
    assert "ConditionPathExists=/etc/sg-gateway/sgnet.json" in unit
    assert "ConditionPathExists=/usr/local/bin/sgnet-server" in unit
    assert "NoNewPrivileges=true" in unit
    assert "PrivateTmp=true" in unit
    assert "ProtectHome=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "LimitNOFILE=1048576" in unit
    assert "CAP_NET_BIND_SERVICE" not in unit
    assert "AmbientCapabilities" not in unit


def test_installer_tracks_sgnet_unit_and_binary_as_managed_paths():
    source = (ROOT / "deploy/install-core.sh").read_text(encoding="utf-8")
    assert "etc/systemd/system/sg-gateway-sgnet.service" in source
    assert "usr/local/bin/sgnet-server" in source
    assert (
        'install -m 0644 "$PREFIX/deploy/sg-gateway-sgnet.service" '
        "/etc/systemd/system/sg-gateway-sgnet.service"
    ) in source


def test_update_safety_backup_tracks_sgnet_runtime_state():
    source = (ROOT / "deploy/update-from-github-core.sh").read_text(encoding="utf-8")
    assert 'SGNET_SERVICE="sg-gateway-sgnet.service"' in source
    assert 'SGNET_CONFIG="$(system_path /etc/sg-gateway/sgnet.json)"' in source
    assert 'SGNET_UNIT="$(system_path /etc/systemd/system/sg-gateway-sgnet.service)"' in source
    assert 'SGNET_BINARY="$(system_path /usr/local/bin/sgnet-server)"' in source
    assert '"$SGNET_CONFIG" "$SGNET_UNIT" "$SGNET_BINARY"' in source
    assert '"$SGNET_SERVICE"' in source


def test_release_manifest_declares_sgnet_but_keeps_binary_delivery_gate_explicit():
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    sgnet = manifest["sgnet"]
    assert sgnet["engine"] == "sgnet"
    assert sgnet["protocol_version"] == 1
    assert sgnet["runtime_version"] == "0.1.0"
    assert sgnet["internal_listener"] == "127.0.0.1:10448"
    assert sgnet["public_tcp_port"] == 443
    assert sgnet["service"] == "sg-gateway-sgnet.service"
    assert sgnet["binary"] == "/usr/local/bin/sgnet-server"
    assert sgnet["binary_delivery"] == "prebuilt-release-artifact-required-before-production"

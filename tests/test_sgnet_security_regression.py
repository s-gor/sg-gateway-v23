from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_server_completes_tls_handshake_before_sgnet_frames():
    source = (ROOT / "runtime/sgnet/internal/server/server.go").read_text(encoding="utf-8")
    handle = source[source.index("func (s *Server) handle"):source.index("func parseDestination")]
    handshake = handle.index("tc.Handshake()")
    framed = handle.index("newFramedConn(c)")
    first_write = handle.index("f.writeFrame(")
    assert handshake < framed < first_write


def test_public_single_edge_has_no_sgnet_specific_alpn():
    source = (ROOT / "deploy/configure-panel-access.sh").read_text(encoding="utf-8").lower()
    assert "alpn sg-net" not in source
    assert "alpn sgnet" not in source
    assert "ssl_preread on;" in source


def test_runtime_status_allowlist_cannot_return_device_secret():
    source = (ROOT / "hostd/sg_hostd/sgnet_runtime.py").read_text(encoding="utf-8")
    health_start = source.index("def _health(")
    health_end = source.index("def test_candidate(", health_start)
    health = source[health_start:health_end]
    assert '"secret"' not in health
    assert '"private_key"' not in health
    assert '"credential"' not in health


def test_access_ui_never_places_sgnet_profile_secret_in_html_payload():
    source = (ROOT / "app/clients/access.py").read_text(encoding="utf-8")
    start = source.index('sgnet = deployments.get("sgnet")')
    end = source.index('sgclient = deployments.get("sgclient")', start)
    block = source[start:end]
    assert 'payload=""' in block
    assert "build_sgnet_config" not in block


def test_sgnet_runtime_does_not_log_config_or_secret_values():
    files = [
        ROOT / "runtime/sgnet/cmd/sgnet-server/main.go",
        ROOT / "runtime/sgnet/internal/server/server.go",
        ROOT / "hostd/sg_hostd/sgnet_runtime.py",
    ]
    for path in files:
        body = path.read_text(encoding="utf-8")
        lowered = body.lower()
        assert 'print(payload' not in lowered
        assert 'println(payload' not in lowered
        assert 'log.Printf("secret' not in body
        assert 'message=f"secret' not in body


def test_no_public_sgnet_uri_scheme_is_defined():
    files = [
        ROOT / "app/clients/exports.py",
        ROOT / "app/clients/sg_subscription.py",
        ROOT / "app/sgnet/service.py",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "sgnet://" not in joined

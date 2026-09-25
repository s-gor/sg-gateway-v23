from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cascade import runtime as cascade
from app.routing import runtime


def _outbound() -> dict:
    return {
        "tag": "anything-user-supplied",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": "gateway-b.example",
                    "port": 443,
                    "users": [
                        {
                            "id": "11111111-2222-3333-4444-555555555555",
                            "encryption": "none",
                            "flow": "xtls-rprx-vision",
                        }
                    ],
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "serverName": "gateway-b.example",
                "fingerprint": "firefox",
                "publicKey": "public-key",
                "shortId": "abcd1234",
            },
        },
    }


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SG_GATEWAY_CASCADE_STATE_PATH", str(tmp_path / "cascade.json"))
    monkeypatch.setenv("SG_GATEWAY_XRAY_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("SG_GATEWAY_ROUTING_MANAGED_PATH", str(tmp_path / "routing.json"))


def _mark_tested(tmp_path: Path, *, ipv4: bool = True, ipv6: bool = False, enabled: bool = True) -> None:
    path = tmp_path / "cascade.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["families"] = {"ipv4": ipv4, "ipv6": ipv6}
    payload["enabled"] = enabled
    payload["last_test"] = {
        "ok": ipv4 or ipv6,
        "ipv4": {"ok": ipv4, "ip": "203.0.113.7" if ipv4 else ""},
        "ipv6": {"ok": ipv6, "ip": "2001:db8::7" if ipv6 else ""},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cascade_normalizes_user_tag_and_preserves_transport(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    source = _outbound()
    source["routing"] = {"rules": [{"outboundTag": "evil"}]}
    normalized = cascade.normalize_outbound(source)
    assert normalized["tag"] == "cascade-core"
    assert normalized["protocol"] == "vless"
    assert normalized["streamSettings"]["security"] == "reality"
    assert "routing" not in normalized


def test_cascade_state_is_fail_closed_until_real_test(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    cascade.configure(_outbound(), ipv4_ready=True, ipv6_ready=False)
    assert cascade.enabled() is False
    assert cascade.family_capabilities() == {"ipv4": False, "ipv6": False}
    overview = cascade.overview()
    assert overview["endpoint"] == "gateway-b.example:443"
    assert overview["ipv4_ready"] is False
    with pytest.raises(cascade.CascadeError, match="семейства IP"):
        cascade.enable()


def test_cascade_rejects_non_vless_outbound(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    bad = _outbound()
    bad["protocol"] = "freedom"
    with pytest.raises(cascade.CascadeError, match="VLESS"):
        cascade.configure(bad)


def test_routing_build_adds_cascade4_only_when_ready(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    cascade.configure(_outbound(), ipv4_ready=True, ipv6_ready=False)
    _mark_tested(tmp_path, ipv4=True, ipv6=False, enabled=True)
    config = runtime.build_full_config(
        {"routing": {"rules": [{"type": "field", "network": "tcp,udp", "outboundTag": "cascade4"}]}},
        base_config={"inbounds": [], "outbounds": []},
    )
    tags = [item.get("tag") for item in config["outbounds"]]
    assert "cascade-core" in tags
    assert "cascade4" in tags
    assert "cascade6" not in tags
    gate = next(item for item in config["outbounds"] if item.get("tag") == "cascade4")
    assert gate["streamSettings"]["sockopt"]["dialerProxy"] == "cascade-core"


def test_cascade6_rule_is_rejected_when_family_not_ready(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    cascade.configure(_outbound(), ipv4_ready=True, ipv6_ready=False)
    _mark_tested(tmp_path, ipv4=True, ipv6=False, enabled=True)
    with pytest.raises(runtime.RoutingRuntimeError, match="Cascade.*IPv6"):
        runtime.sanitize_managed_fragment(
            {"routing": {"rules": [{"type": "field", "network": "tcp", "outboundTag": "cascade6"}]}}
        )


def test_disabled_cascade_rule_is_rejected(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    cascade.configure(_outbound(), ipv4_ready=True)
    _mark_tested(tmp_path, ipv4=True, enabled=True)
    cascade.disable()
    with pytest.raises(runtime.RoutingRuntimeError, match="Cascade"):
        runtime.sanitize_managed_fragment(
            {"routing": {"rules": [{"type": "field", "network": "tcp", "outboundTag": "cascade4"}]}}
        )

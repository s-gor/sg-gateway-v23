from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.routing import external
from app.routing import runtime


@pytest.fixture()
def external_state(monkeypatch, tmp_path):
    path = tmp_path / "external.json"
    monkeypatch.setenv("SG_GATEWAY_EXTERNAL_OUTBOUNDS_PATH", str(path))
    return path


def test_external_socks_and_http_build_xray_outbounds(external_state):
    first = external.save_outbound(
        name="France",
        protocol="socks",
        host="fr.example.net",
        port="1080",
        username="sg",
        password="secret",
    )
    second = external.save_outbound(
        name="Germany",
        protocol="http",
        host="de.example.net",
        port=3128,
    )

    assert first["tag"] == "ext-france"
    assert second["tag"] == "ext-germany"
    built = {item["tag"]: item for item in external.build_xray_outbounds()}
    assert built["ext-france"] == {
        "tag": "ext-france",
        "protocol": "socks",
        "settings": {
            "servers": [{
                "address": "fr.example.net",
                "port": 1080,
                "users": [{"user": "sg", "pass": "secret"}],
            }]
        },
    }
    assert built["ext-germany"]["protocol"] == "http"
    assert built["ext-germany"]["settings"]["servers"][0]["port"] == 3128


def test_external_overview_never_returns_password(external_state):
    external.save_outbound(
        name="Private",
        protocol="socks",
        host="proxy.example.net",
        port=1080,
        username="user",
        password="do-not-render",
    )
    item = external.overview()["outbounds"][0]
    assert item["has_password"] is True
    assert "password" not in item
    assert "do-not-render" not in json.dumps(item)


def test_runtime_accepts_enabled_external_tag_and_injects_outbound(external_state, monkeypatch):
    external.save_outbound(
        name="France",
        protocol="socks",
        host="fr.example.net",
        port=1080,
    )
    monkeypatch.setattr(runtime, "routing_capabilities", lambda: {
        "direct4": True, "direct6": False, "warp4": False,
        "warp6": False, "block": True, "warp_enabled": False,
    })
    fragment = runtime.sanitize_managed_fragment({
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [{
                "type": "field",
                "domain": ["domain:example.com"],
                "outboundTag": "ext-france",
            }],
        }
    })
    assert fragment["routing"]["rules"][0]["outboundTag"] == "ext-france"
    outbounds = runtime.build_managed_outbounds([])
    assert "ext-france" in {item["tag"] for item in outbounds}


def test_remove_external_is_blocked_while_active_routing_uses_it(external_state, monkeypatch):
    item = external.save_outbound(
        name="France",
        protocol="socks",
        host="fr.example.net",
        port=1080,
    )
    monkeypatch.setattr(
        runtime,
        "load_managed_fragment",
        lambda: {"routing": {"rules": [{"outboundTag": item["tag"]}]}},
    )
    with pytest.raises(external.ExternalOutboundError, match="используется активным Routing"):
        external.remove_and_apply(item["id"])


def test_outbounds_and_routing_ui_expose_external_controls():
    root = Path(__file__).resolve().parents[1]
    outbounds = (root / "app/web/templates/outbounds.html").read_text(encoding="utf-8")
    routing = (root / "app/web/templates/routing.html").read_text(encoding="utf-8")
    main = (root / "app/main.py").read_text(encoding="utf-8")

    assert "outbounds_external_create" in outbounds
    assert "outbounds_external_remove" in outbounds
    assert 'name="protocol"' in outbounds
    assert "SOCKS5" in outbounds
    assert "HTTP CONNECT" in outbounds
    assert "external_outbounds.outbounds" in routing
    assert '@app.post("/outbounds/external/create")' in main
    assert '@app.post("/outbounds/external/<identifier>/remove")' in main


def test_failover_group_compiles_primary_fallback_and_observatory(external_state):
    primary = external.save_outbound(
        name="Primary",
        protocol="socks",
        host="primary.example.net",
        port=1080,
    )
    backup = external.save_outbound(
        name="Backup",
        protocol="http",
        host="backup.example.net",
        port=3128,
    )
    group = external.save_group(
        name="EU Failover",
        members=[primary["tag"], backup["tag"]],
        strategy="failover",
    )
    balancer = external.build_xray_balancers()[0]
    assert balancer["tag"] == group["tag"]
    assert balancer["selector"] == [primary["tag"]]
    assert balancer["fallbackTag"] == backup["tag"]
    assert balancer["strategy"] == {"type": "random"}
    observatory = external.build_xray_observatory()
    assert observatory is not None
    assert observatory["subjectSelector"] == [primary["tag"]]
    assert observatory["probeInterval"] == "30s"


def test_group_action_is_sanitized_to_balancer_tag(external_state, monkeypatch):
    one = external.save_outbound(name="One", protocol="socks", host="one.example.net", port=1080)
    two = external.save_outbound(name="Two", protocol="socks", host="two.example.net", port=1080)
    group = external.save_group(name="Pool", members=[one["tag"], two["tag"]], strategy="roundRobin")
    monkeypatch.setattr(runtime, "routing_capabilities", lambda: {
        "direct4": True, "direct6": False, "warp4": False,
        "warp6": False, "block": True, "warp_enabled": False,
    })
    fragment = runtime.sanitize_managed_fragment({
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [{
                "type": "field",
                "domain": ["domain:example.com"],
                "outboundTag": group["tag"],
            }],
        }
    })
    rule = fragment["routing"]["rules"][0]
    assert rule["balancerTag"] == group["tag"]
    assert "outboundTag" not in rule


def test_failover_group_requires_exactly_two_members(external_state):
    one = external.save_outbound(name="One", protocol="socks", host="one.example.net", port=1080)
    with pytest.raises(external.ExternalOutboundError, match="ровно два"):
        external.save_group(name="Bad", members=[one["tag"]], strategy="failover")

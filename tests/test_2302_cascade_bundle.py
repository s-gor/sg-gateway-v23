from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cascade import runtime
from app.cascade.adapters import xray_outbound
from app.cascade.bundle import BUNDLE_FORMAT, CHANNEL_SPECS, validate_bundle


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / "cascade.json"
    monkeypatch.setenv("SG_GATEWAY_CASCADE_STATE_PATH", str(state))
    monkeypatch.setenv("SG_GATEWAY_XRAY_CONFIG", str(tmp_path / "xray.json"))
    monkeypatch.setenv("SG_GATEWAY_ROUTING_MANAGED_PATH", str(tmp_path / "routing.json"))
    return state


def _bundle() -> dict:
    payloads = {
        "reality_tcp": "vless://11111111-2222-3333-4444-555555555555@gw.example:443?type=tcp&security=reality&flow=xtls-rprx-vision&sni=www.bing.com&fp=chrome&pbk=pk&sid=abcd#Reality",
        "xhttp_reality": "vless://11111111-2222-3333-4444-555555555555@gw.example:443?type=xhttp&security=reality&sni=www.bing.com&fp=chrome&pbk=pk&sid=abcd&path=%2Fsg&mode=stream-one&encryption=mlkem768x25519plus.native.0rtt#XHTTP",
        "xhttp_tls": "vless://11111111-2222-3333-4444-555555555555@gw.example:443?type=xhttp&security=tls&sni=gw.example&alpn=h2&path=%2Fsgtls&mode=auto&encryption=mlkem768x25519plus.native.0rtt#XHTTP-TLS",
        "hysteria2": "hysteria2://secret@gw.example:443/?sni=gw.example&insecure=0#H2",
        "awg31": "awg31://import/v1/test-payload",
        "mieru": "mierus://user:pass@gw.example?profile=default&port=443&protocol=TCP&multiplexing=MULTIPLEXING_LOW&handshake-mode=HANDSHAKE_STANDARD#Mieru",
        "anytls": "anytls://secret@gw.example:443?security=tls&sni=gw.example&alpn=sg-anytls&fp=chrome&type=tcp#AnyTLS",
        "tuic": "tuic://11111111-2222-3333-4444-555555555555:secret@gw.example:443?congestion_control=bbr&udp_relay_mode=native&alpn=h3&sni=gw.example#TUIC",
        "naiveproxy": "naive+https://user:secret-password@gw.example:443#Naive",
    }
    return {
        "format": BUNDLE_FORMAT,
        "created_at": "2026-09-25T08:00:00+00:00",
        "channels": [
            {
                "id": channel_id,
                "title": title,
                "kind": kind,
                "engine": engine,
                "payload": payloads[channel_id],
            }
            for channel_id, title, kind, engine in CHANNEL_SPECS
        ],
    }


def _mark_all_ready(path: Path) -> None:
    state = json.loads(path.read_text(encoding="utf-8"))
    for channel in state["channels"].values():
        channel["ready"] = True
        channel["status"] = "ready"
        channel["last_test"] = {
            "ok": True,
            "ipv4": {"ok": True, "ip": "203.0.113.77"},
            "ipv6": {"ok": False, "ip": ""},
        }
    state["families"] = {"ipv4": True, "ipv6": False}
    state["last_test"] = {
        "ok": True,
        "ready_count": 9,
        "required_count": 9,
        "checked_at": "2026-09-25T08:01:00+00:00",
    }
    path.write_text(json.dumps(state), encoding="utf-8")


def test_bundle_requires_all_nine_channels():
    checked = validate_bundle(_bundle())
    assert checked["complete"] is True
    assert len(checked["present"]) == 9
    broken = _bundle()
    broken["channels"] = broken["channels"][:-1]
    checked = validate_bundle(broken)
    assert checked["complete"] is False
    assert len(checked["missing"]) == 1


def test_import_creates_nine_independent_channel_states(monkeypatch, tmp_path):
    state = _env(monkeypatch, tmp_path)
    result = runtime.import_bundle(_bundle(), name="Exit Amsterdam")
    assert state.is_file()
    assert result["configured"] is True
    assert result["ready_count"] == 0
    assert result["required_count"] == 9
    assert len(result["channels"]) == 9
    assert {item["status"] for item in result["channels"]} == {"unchecked"}


def test_enable_is_strictly_nine_of_nine(monkeypatch, tmp_path):
    state = _env(monkeypatch, tmp_path)
    runtime.import_bundle(_bundle())
    raw = json.loads(state.read_text())
    for channel in raw["channels"].values():
        channel["ready"] = True
        channel["status"] = "ready"
    raw["channels"]["naiveproxy"]["ready"] = False
    raw["families"] = {"ipv4": True, "ipv6": False}
    state.write_text(json.dumps(raw))
    with pytest.raises(runtime.CascadeError, match="9/9.*naiveproxy"):
        runtime.enable()


def test_auto_and_manual_select_real_channel(monkeypatch, tmp_path):
    state = _env(monkeypatch, tmp_path)
    runtime.import_bundle(_bundle())
    _mark_all_ready(state)

    enabled = runtime.enable()
    assert enabled["enabled"] is True
    assert enabled["active_channel"] == "reality_tcp"
    core = runtime.outbound()
    assert core["protocol"] == "socks"
    assert core["settings"]["servers"][0] == {"address": "127.0.0.1", "port": 10490}

    manual = runtime.set_mode("manual", manual_channel="anytls")
    assert manual["active_channel"] == "anytls"
    assert runtime.outbound()["settings"]["servers"][0]["address"] == "127.0.0.1"

    awg = runtime.set_mode("manual", manual_channel="awg31")
    assert awg["active_channel"] == "awg31"
    assert runtime.outbound()["settings"]["servers"][0] == {"address": "169.254.231.2", "port": 10490}


def test_priority_reorders_auto_selection(monkeypatch, tmp_path):
    state = _env(monkeypatch, tmp_path)
    runtime.import_bundle(_bundle())
    _mark_all_ready(state)
    runtime.set_mode("priority", priority=["anytls", "tuic", "hysteria2"])
    result = runtime.enable()
    assert result["active_channel"] == "anytls"


def test_xray_adapter_preserves_reality_and_xhttp_contracts():
    checked = validate_bundle(_bundle())
    by_id = {item["id"]: item for item in checked["channels"]}

    reality = xray_outbound(by_id["reality_tcp"])
    assert reality["protocol"] == "vless"
    assert reality["streamSettings"]["security"] == "reality"
    assert reality["streamSettings"]["realitySettings"]["publicKey"] == "pk"

    xhttp = xray_outbound(by_id["xhttp_reality"])
    assert xhttp["streamSettings"]["network"] == "xhttp"
    assert xhttp["streamSettings"]["xhttpSettings"]["path"] == "/sg"
    assert xhttp["streamSettings"]["xhttpSettings"]["mode"] == "stream-one"

    hysteria = xray_outbound(by_id["hysteria2"])
    assert hysteria["protocol"] == "hysteria"
    assert hysteria["settings"]["version"] == 2

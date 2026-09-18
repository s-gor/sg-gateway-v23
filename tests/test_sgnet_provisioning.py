from __future__ import annotations

import json
from types import SimpleNamespace

from app.engines import provisioning
from app.sgnet.credentials import secret_bytes


def _settings():
    return SimpleNamespace(
        host="vpn.example.com",
        port=443,
        config={"server_name": "edge.example.com"},
    )


def test_sgnet_devices_get_independent_256_bit_secrets(monkeypatch):
    monkeypatch.setattr(provisioning, "get_connection_settings", lambda engine: _settings())

    object1, raw1 = provisioning.build_engine_config("sgnet", 101, "Phone")
    object2, raw2 = provisioning.build_engine_config("sgnet", 102, "Laptop")
    one = json.loads(raw1)
    two = json.loads(raw2)

    assert object1 == "sgnet-101"
    assert object2 == "sgnet-102"
    assert one["secret"] != two["secret"]
    assert len(secret_bytes(one["secret"])) == 32
    assert len(secret_bytes(two["secret"])) == 32
    assert one["type"] == "sg-net"
    assert one["protocol_version"] == 1
    assert one["server"] == "vpn.example.com"
    assert one["port"] == 443
    assert one["server_name"] == "edge.example.com"
    assert one["transports"] == ["sg-tls"]
    assert one["capabilities"] == ["tcp", "udp", "mux"]


def test_sgnet_object_id_does_not_embed_secret(monkeypatch):
    monkeypatch.setattr(provisioning, "get_connection_settings", lambda engine: _settings())
    object_id, raw = provisioning.build_engine_config("sgnet", 7, "Phone")
    payload = json.loads(raw)
    assert payload["secret"] not in object_id
    assert object_id == "sgnet-7"

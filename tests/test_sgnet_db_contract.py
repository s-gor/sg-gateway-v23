from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import app.db as db
from app.single_edge import SGNET_INTERNAL_PORT


def _use_database(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(db, "load_config", lambda: SimpleNamespace(data_dir=data_dir))
    return data_dir / "sg-gateway.sqlite"


def test_fresh_database_seeds_disabled_sgnet_without_credentials(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    db.init_db()

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT enabled, host, port, config_json FROM connection_settings WHERE engine='sgnet'"
        ).fetchone()
        credentials = conn.execute(
            "SELECT COUNT(*) FROM device_credentials WHERE engine='sgnet'"
        ).fetchone()[0]

    assert row is not None
    assert row["enabled"] == 0
    assert row["host"] == ""
    assert row["port"] == 443
    config = json.loads(row["config_json"])
    assert config["internal_host"] == "127.0.0.1"
    assert config["internal_port"] == SGNET_INTERNAL_PORT
    assert config["server_name"] == ""
    assert config["transports"] == ["sg-tls"]
    assert credentials == 0


def test_old_database_gets_only_disabled_infrastructure_row(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute(
            "INSERT INTO connection_settings(engine, enabled, host, port, config_json) "
            "VALUES('xray', 1, 'old.example', 443, '{}')"
        )

    db.init_db()

    with sqlite3.connect(path) as conn:
        sgnet = conn.execute(
            "SELECT enabled FROM connection_settings WHERE engine='sgnet'"
        ).fetchone()
        xray = conn.execute(
            "SELECT enabled, host FROM connection_settings WHERE engine='xray'"
        ).fetchone()
        credentials = conn.execute(
            "SELECT COUNT(*) FROM device_credentials WHERE engine='sgnet'"
        ).fetchone()[0]

    assert sgnet == (0,)
    assert xray == (1, "old.example")
    assert credentials == 0


def test_existing_default_engines_remain_enabled(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    db.init_db()
    with sqlite3.connect(path) as conn:
        rows = dict(conn.execute(
            "SELECT engine, enabled FROM connection_settings "
            "WHERE engine IN ('xray','mihomo','amneziawg31')"
        ).fetchall())
    assert rows == {"xray": 1, "mihomo": 1, "amneziawg31": 1}

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import app.db as db
from app.clients.repository import restore_client_snapshot, snapshot_client
from sg_hostd import clients_keys_backup_patch


def _use_database(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(db, "load_config", lambda: SimpleNamespace(data_dir=data_dir))
    import app.clients.repository as repository
    monkeypatch.setattr(repository, "connect", db.connect)
    monkeypatch.setattr(repository, "init_db", db.init_db)
    return data_dir / "sg-gateway.sqlite"


def test_client_snapshot_restore_preserves_sgnet_config_json_byte_for_byte(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    db.init_db()
    raw = '{  "secret" : "A_PRIVATE_VALUE" , "type":"sg-net","protocol_version":1 }'
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO clients(id,name,enabled) VALUES(1,'Alice',1)")
        conn.execute(
            "INSERT INTO devices(id,client_id,name,enabled,is_primary) "
            "VALUES(10,1,'Phone',1,1)"
        )
        conn.execute(
            "INSERT INTO device_credentials(id,device_id,engine,status,engine_object_id,config_json) "
            "VALUES(100,10,'sgnet','applied','sgnet-10',?)",
            (raw,),
        )

    snapshot = snapshot_client(1)
    assert snapshot is not None
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE device_credentials SET config_json='{}' WHERE id=100")
    assert restore_client_snapshot(snapshot) is True

    with sqlite3.connect(path) as conn:
        restored = conn.execute(
            "SELECT config_json FROM device_credentials WHERE id=100"
        ).fetchone()[0]
    assert restored == raw


def test_portable_rebind_explicitly_skips_sgnet_reserialization():
    source = Path(clients_keys_backup_patch.__file__).read_text(encoding="utf-8")
    assert 'engine in {"amneziawg31", "sgnet"}' in source
    marker = source.index('engine in {"amneziawg31", "sgnet"}')
    assert "continue" in source[marker:marker + 500]


def test_old_backup_database_without_sgnet_credentials_stays_dormant(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute(
            "INSERT INTO clients(id,name,enabled) VALUES(1,'Legacy',1)"
        )
        conn.execute(
            "INSERT INTO devices(id,client_id,name,enabled,is_primary) "
            "VALUES(10,1,'Phone',1,1)"
        )

    db.init_db()

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT enabled, host FROM connection_settings WHERE engine='sgnet'"
        ).fetchone()
        count = conn.execute(
            "SELECT COUNT(*) FROM device_credentials WHERE engine='sgnet'"
        ).fetchone()[0]
    assert row == (0, "")
    assert count == 0


def test_sgnet_restore_does_not_touch_unrelated_credential_json(monkeypatch, tmp_path):
    path = _use_database(monkeypatch, tmp_path)
    db.init_db()
    xray_raw = '{"uuid":"keep-exactly-this"}'
    sgnet_raw = '{"secret":"keep-sg-secret","type":"sg-net"}'
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO clients(id,name,enabled) VALUES(1,'Alice',1)")
        conn.execute(
            "INSERT INTO devices(id,client_id,name,enabled,is_primary) "
            "VALUES(10,1,'Phone',1,1)"
        )
        conn.execute(
            "INSERT INTO device_credentials(id,device_id,engine,status,config_json) "
            "VALUES(100,10,'xray','applied',?)",
            (xray_raw,),
        )
        conn.execute(
            "INSERT INTO device_credentials(id,device_id,engine,status,config_json) "
            "VALUES(101,10,'sgnet','applied',?)",
            (sgnet_raw,),
        )

    snapshot = snapshot_client(1)
    assert snapshot is not None
    assert restore_client_snapshot(snapshot)

    with sqlite3.connect(path) as conn:
        rows = dict(conn.execute(
            "SELECT engine, config_json FROM device_credentials WHERE device_id=10"
        ).fetchall())
    assert rows["xray"] == xray_raw
    assert rows["sgnet"] == sgnet_raw

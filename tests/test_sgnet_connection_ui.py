from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_connections_template_has_safe_sgnet_panel():
    body = (ROOT / "app/web/templates/connections.html").read_text(encoding="utf-8")
    assert 'id="sgnet"' in body
    assert "SG-Net/1" in body
    assert "SG-TLS" in body
    assert "loopback :10448" in body
    assert 'action="{{ url_for(\'update_sgnet\') }}"' in body
    assert 'name="server_name"' in body
    assert 'name="certificate_path"' in body
    assert 'name="private_key_path"' in body
    assert 'name="secret"' not in body
    assert "config_json" not in body


def test_client_detail_does_not_render_sgnet_secret_directly():
    access = (ROOT / "app/clients/access.py").read_text(encoding="utf-8")
    marker = 'kind="sgnet"'
    start = access.index(marker)
    block = access[start:start + 900]
    assert 'title="SG-Net"' in block
    assert 'payload=""' in block
    assert "show_qr=False" in block


def test_sgnet_settings_route_uses_privileged_runtime_commands():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert '@app.post("/connections/sgnet")' in main
    assert '"test": "sgnet.test"' in main
    assert '"apply": "sgnet.apply"' in main
    assert '"restart": "sgnet.restart"' in main
    assert '"rollback": "sgnet.rollback"' in main
    assert 'run_hostd_command(command, timeout=120)' in main


def test_sgnet_settings_reject_protocol_identifying_hostname():
    service = (ROOT / "app/sgnet/service.py").read_text(encoding="utf-8")
    assert '"sgnet" in domain or "sg-net" in domain' in service
    assert 'raise SgNetSettingsError("TLS-имя не должно раскрывать название SG-Net")' in service

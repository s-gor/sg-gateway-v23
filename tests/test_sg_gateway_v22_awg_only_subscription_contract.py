from pathlib import Path

from jinja2 import Environment

from app.main import _prepare_client_protocols


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
CLIENTS = ROOT / "app" / "web" / "templates" / "clients.html"
DETAIL = ROOT / "app" / "web" / "templates" / "client_detail.html"
EDIT = ROOT / "app" / "web" / "templates" / "_client_edit_dialogs.html"
HELP = ROOT / "app" / "help" / "content.py"
JS = ROOT / "app" / "web" / "static" / "sg-awg-only-notice-v1.js"


def test_awg_only_protocols_create_without_subscription():
    assert _prepare_client_protocols(
        ["sgclient", "amneziawg", "amneziawg3", "amneziawg31"]
    ) == ["amneziawg", "amneziawg3", "amneziawg31"]


def test_non_awg_protocol_adds_single_subscription_credential():
    assert _prepare_client_protocols(
        ["amneziawg", "mihomo", "sgclient", "mihomo"]
    ) == ["amneziawg", "mihomo", "sgclient"]
    assert _prepare_client_protocols(
        ["xray_reality_tcp"]
    ) == ["xray_reality_tcp", "sgclient"]


def test_all_client_and_device_mutations_use_protocol_normalizer():
    source = MAIN.read_text(encoding="utf-8")
    prepared = (
        'protocols = _prepare_client_protocols('
        'request.form.getlist("protocols"))'
    )
    assert source.count(prepared) == 4
    assert 'protocols = request.form.getlist("protocols")' not in source


def test_awg_only_notice_highlights_only_nonempty_all_awg_selection():
    source = JS.read_text(encoding="utf-8")
    assert "selected.length > 0" in source
    assert "selected.every(value => awgOnlyValues.has(value))" in source
    assert "value !== 'sgclient'" in source


def test_help_explains_awg_only_creation_contract():
    source = HELP.read_text(encoding="utf-8")
    assert "SG_GATEWAY_02206_AWG_ONLY_NOTICE_HELP_V2" in source
    assert "клиент и соединения создаются нормально" in source
    assert "SG Client subscription не формируется" in source

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "web" / "static"


def test_clients_page_title_uses_same_two_layer_contract_as_system():
    system_visual = (STATIC / "sg-system-visual-v1.css").read_text(encoding="utf-8")
    clients_visual = (STATIC / "sg-clients-visual-v2.css").read_text(encoding="utf-8")
    system_ui = (STATIC / "sg-ui-system-v22-08.css").read_text(encoding="utf-8")
    clients_ui = (STATIC / "sg-ui-clients-v22-08.css").read_text(encoding="utf-8")

    assert ".sv1-heading h1 {" in system_visual
    assert "margin: 7px 0 4px;" in system_visual
    assert ".cv2-heading h1 {" in clients_visual
    assert "margin: 7px 0 4px;" in clients_visual

    assert ".sg-ui-system-head h1 {" in system_ui
    assert "font-size: 27px;" in system_ui
    assert "line-height: 1.05;" in system_ui

    selector = '[data-sg-ui-page="clients"] > .sg-ui-page-head h1'
    assert selector in clients_ui
    assert "font-size: 27px;" in clients_ui
    assert "line-height: 1.05;" in clients_ui
    assert "font-weight:" not in clients_ui.split(selector, 1)[1].split("}", 1)[0]
    assert "letter-spacing:" not in clients_ui.split(selector, 1)[1].split("}", 1)[0]


def test_legacy_routing_frame_no_longer_overrides_clients_heading():
    legacy = (STATIC / "sg-page-frame-routing-v1.css").read_text(encoding="utf-8")
    assert ".cv2-heading.cv15-heading" not in legacy
    assert ":is(.cv2-kicker," not in legacy
    assert ".cv2-heading-actions-actions" not in legacy


def test_client_name_matches_device_count_size():
    css = (STATIC / "sg-clients-clarity-hotfix2.css").read_text(encoding="utf-8")
    assert "body.clients-clarity-hotfix2 .cv15-client-cell strong {" in css
    assert "font-size: 17px;" in css
    assert "body.clients-clarity-hotfix2 .cv15-device-count strong {" in css

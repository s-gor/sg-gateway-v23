from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "web" / "static"


def test_clients_page_title_matches_system_visual_size_and_spacing():
    system = (STATIC / "sg-system-visual-v1.css").read_text(encoding="utf-8")
    clients = (STATIC / "sg-ui-clients-v22-08.css").read_text(encoding="utf-8")

    assert ".sv1-heading h1 {" in system
    assert "margin: 7px 0 4px;" in system

    selector = '[data-sg-ui-page="clients"] > .sg-ui-page-head h1'
    assert selector in clients
    for fragment in (
        "margin: 7px 0 4px !important;",
        "font-size: 27px !important;",
        "line-height: 1.05 !important;",
        "font-weight: 700 !important;",
        "letter-spacing: normal !important;",
    ):
        assert fragment in clients


def test_client_name_matches_device_count_size():
    css = (STATIC / "sg-clients-clarity-hotfix2.css").read_text(encoding="utf-8")
    assert "body.clients-clarity-hotfix2 .cv15-client-cell strong {" in css
    assert "font-size: 17px;" in css
    assert "body.clients-clarity-hotfix2 .cv15-device-count strong {" in css

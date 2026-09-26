from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "web" / "templates" / "base.html"
STATIC = ROOT / "app" / "web" / "static"


def test_clients_loads_shared_connections_dark_layer():
    source = BASE.read_text(encoding="utf-8")
    assert "active_page|default('') in ['connections', 'cascade', 'security', 'clients']" in source
    assert "sg-connections-dark-classic-v1.css" in source


def test_clients_typography_matches_connections_scale():
    readable = (STATIC / "sg-clients-readable-small-v1.css").read_text(encoding="utf-8")
    for fragment in (
        ".cv2-kicker { font-size:9px; }",
        ".cv2-heading-copy > p { font-size:13.5px;",
        ".cv2-filter-field > span { font-size:7.5px; }",
        ".cv2-filter-field select { font-size:10px; }",
        ".cv2-table thead th { font-size:7.5px; }",
    ):
        assert fragment in readable

    page = (STATIC / "sg-ui-clients-v22-08.css").read_text(encoding="utf-8")
    visual = (STATIC / "sg-clients-visual-v2.css").read_text(encoding="utf-8")
    assert "min-height: 68px;" in page
    assert "padding: 4px 0 10px;" in page
    assert '[data-sg-ui-page="clients"] > .sg-ui-page-head h1' not in page
    assert ".cv2-heading h1 {" in visual
    assert "font-size: clamp(31px, 2.25vw, 38px);" in visual
    assert "min-height: 43px;" in page
    assert "font-size: 9px;" in page


def test_clients_uses_connections_dark_palette_and_depth():
    css = (STATIC / "sg-connections-dark-classic-v1.css").read_text(encoding="utf-8")
    assert 'body:is(.page-connections, .page-cascade, .page-security, .page-clients)' in css
    for fragment in (
        "html[data-theme=\"dark\"] body.page-clients :is(",
        ".cv15-filter-panel,",
        ".cv15-list-panel,",
        "#sg-0217-sg-admin-explainer",
        "border-color: #355a7c !important;",
        "linear-gradient(180deg, #1a2e43 0%, #15263a 100%) !important;",
        "0 15px 36px rgba(0, 0, 0, .18) !important;",
        "background: linear-gradient(180deg, #0f2032 0%, #0b1826 100%) !important;",
    ):
        assert fragment in css

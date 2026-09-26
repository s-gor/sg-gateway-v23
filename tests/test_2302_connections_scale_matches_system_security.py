from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "web" / "static"
TEMPLATES = ROOT / "app" / "web" / "templates"


def test_connections_uses_explicit_shared_page_hooks():
    source = (TEMPLATES / "connections.html").read_text(encoding="utf-8")
    assert 'data-sg-ui-page="connections"' in source
    assert 'sg-ui-connections-head' in source
    assert 'data-sg-section="connections-head"' in source


def _shared_header_contract(path: str, prefix: str) -> tuple[str, ...]:
    source = (STATIC / path).read_text(encoding="utf-8")
    required = (
        "width: 100%;",
        "max-width: none;",
        "min-width: 0;",
        "margin: 0;",
        "padding: 0;",
        "box-sizing: border-box;",
        "margin-inline: 0;",
        "min-height: 68px;",
        "padding-block: 4px 10px;",
        "border-bottom: 1px solid var(--sg-ui-border);",
        "font-size: 27px;",
        "line-height: 1.05;",
    )
    for declaration in required:
        assert declaration in source, f"{path}: missing {declaration}"
    assert prefix in source
    return required


def test_connections_outer_scale_matches_system_security_contract():
    system = _shared_header_contract("sg-ui-system-v22-08.css", ".sg-ui-system-head")
    security = _shared_header_contract("sg-ui-security-v22-08.css", ".sg-ui-security-head")
    connections = _shared_header_contract("sg-ui-connections-v22-08.css", ".sg-ui-connections-head")
    assert connections == system == security


def test_connections_mobile_header_matches_system_security_contract():
    css = (STATIC / "sg-ui-connections-v22-08.css").read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in css
    assert ".sg-ui-connections-head {" in css
    assert "min-height: 0;" in css
    assert ".sg-ui-connections-head .sg-ui-actions {" in css
    assert "width: 100%;" in css

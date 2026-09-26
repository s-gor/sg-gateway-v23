from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "web" / "templates" / "base.html"
STATIC = ROOT / "app" / "web" / "static"


def test_security_loads_shared_connections_dark_layer():
    source = BASE.read_text(encoding="utf-8")
    assert "active_page|default('') in ['connections', 'cascade', 'security']" in source
    assert "sg-connections-dark-classic-v1.css" in source


def test_shared_dark_palette_scope_includes_security():
    css = (STATIC / "sg-connections-dark-classic-v1.css").read_text(encoding="utf-8")
    scope = 'html[data-theme="dark"] body:is(.page-connections, .page-cascade, .page-security)'
    assert scope in css


def test_security_uses_connections_depth_language():
    css = (STATIC / "sg-connections-dark-classic-v1.css").read_text(encoding="utf-8")
    for fragment in (
        "html[data-theme=\"dark\"] body.page-security :is(",
        ".secv2-workflow,",
        ".secv2-password-card,",
        ".secv2-card,",
        ".secv2-summary,",
        ".secv2-progress,",
        ".secv2-checks,",
        "border-color: #355a7c !important;",
        "linear-gradient(180deg, #1a2e43 0%, #15263a 100%) !important;",
        "0 15px 36px rgba(0, 0, 0, .18) !important;",
        "border-color: #2f506f !important;",
        "linear-gradient(180deg, #12243a 0%, #0e1d2d 100%) !important;",
        "0 8px 24px rgba(0, 0, 0, .10) !important;",
        "color: #65a9f3 !important;",
        "background: linear-gradient(180deg, #0f2032 0%, #0b1826 100%) !important;",
    ):
        assert fragment in css

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app" / "web" / "templates" / "base.html"
STATIC = ROOT / "app" / "web" / "static"


def test_cascade_loads_the_connections_dark_classic_layer():
    source = BASE.read_text(encoding="utf-8")
    assert "active_page|default('') in ['connections', 'cascade', 'security']" in source
    assert "sg-connections-dark-classic-v1.css" in source


def test_connections_dark_classic_layer_targets_cascade_too():
    css = (STATIC / "sg-connections-dark-classic-v1.css").read_text(encoding="utf-8")
    shared = 'html[data-theme="dark"] body:is(.page-connections, .page-cascade, .page-security)'
    assert shared in css
    assert 'html[data-theme="dark"] body.page-connections' not in css


def test_cascade_gets_connections_palette_and_depth_surfaces():
    css = (STATIC / "sg-connections-dark-classic-v1.css").read_text(encoding="utf-8")
    for fragment in (
        "--sg-panel: #192738;",
        "--sg-panel-soft: #152435;",
        "--sg-panel-deep: #101d2b;",
        "--sg-line: #2a3c50;",
        "--sg-blue: #65a9f3;",
        ".cnv1-engine-card,",
        ".xps2-selection,",
        ".xps2-parameters,",
        ".cnv1-endpoint-card,",
        ".xps2-choice {",
        ".xps2-parameter-row {",
        "0 15px 36px rgba(0, 0, 0, .18)",
        "0 8px 24px rgba(0, 0, 0, .10)",
    ):
        assert fragment in css

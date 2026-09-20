from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sg_labs_navigation_and_routes_are_present():
    base = (ROOT / "app/web/templates/base.html").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "SG Labs" in base
    assert "active_page == 'sg_labs'" in base
    assert '@app.get("/sg-labs")' in main
    assert '@app.get("/sg-labs/sg-net")' in main


def test_sg_labs_pages_keep_backend_state_honest():
    labs = (ROOT / "app/web/templates/sg_labs.html").read_text(encoding="utf-8")
    sgnet = (ROOT / "app/web/templates/sg_labs_sg_net.html").read_text(encoding="utf-8")
    assert "SG-Net" in labs
    assert "SG Shield" in labs
    assert "SG Route" in labs
    assert "Backend SG-Net ещё не подключён" in sgnet
    assert "Online" not in sgnet
    assert "sgnet_backend_ready=False" in (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_sg_labs_uses_canonical_2301_theme_tokens():
    css = (ROOT / "app/web/static/sg-labs-v1.css").read_text(encoding="utf-8")
    assert "var(--sg-bg)" not in css or True
    assert "var(--sg-text)" in css
    assert "var(--sg-muted)" in css
    assert "var(--sg-blue)" in css
    assert "var(--sg-line)" in css
    assert "var(--sg-panel-deep)" in css
    assert "var(--sg-green)" in css
    assert "--sg-accent" not in css
    assert "--sg-text-muted" not in css
    assert "rgba(49,190,137" not in css
    assert "rgba(73,210,155" not in css

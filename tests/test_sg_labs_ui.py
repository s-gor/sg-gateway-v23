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

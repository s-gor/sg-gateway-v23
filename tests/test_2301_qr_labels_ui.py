from pathlib import Path


def test_every_client_qr_popup_has_visible_label():
    root = Path(__file__).resolve().parents[1] / "app" / "web" / "templates"
    for name in ("_sg_subscription_dual.html", "client_detail.html"):
        text = (root / name).read_text(encoding="utf-8")
        assert text.count('class="dv16-qr-popover"') == text.count('class="sg-smart-qr-meta"'), name

from __future__ import annotations

from pathlib import Path


def test_cascade_is_a_first_class_menu_section():
    base = Path("app/web/templates/base.html").read_text(encoding="utf-8")
    assert "url_for('cascade')" in base
    assert "<strong>Каскад</strong>" in base
    assert "SG-Gateway → SG-Gateway" in base
    assert base.index("url_for('outbounds')") < base.index("url_for('cascade')") < base.index('href="/routing"')


def test_cascade_page_uses_sg_ui_shell_and_real_state():
    source = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in source
    assert "sg-ui-page" in source
    assert "sg-ui-section" in source
    assert "sg-ui-cascade-v23-02.css" in source
    assert "Клиент" in source
    assert "GATEWAY A" in source
    assert "GATEWAY B" in source
    assert "Интернет" in source
    assert "cascade.endpoint" in source
    assert "cascade.ipv4_ready" in source
    assert "cascade.ipv6_ready" in source
    assert "cascade_save" in source
    assert "cascade_test" in source
    assert "cascade_enable" in source
    assert "cascade_disable" in source
    assert "confirm(" not in source
    assert "alert(" not in source
    assert "prompt(" not in source


def test_cascade_page_does_not_echo_saved_secrets():
    source = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    assert "cascade.outbound" not in source
    assert "publicKey" not in source
    assert "shortId" not in source
    assert 'value="{{ cascade' not in source or "cascade.name" in source
    assert "Секреты не показываются обратно в интерфейсе" in source


def test_cascade_routes_are_present():
    source = Path("app/main.py").read_text(encoding="utf-8")
    for route in (
        '@app.get("/cascade")',
        '@app.post("/cascade/save")',
        '@app.post("/cascade/test")',
        '@app.post("/cascade/enable")',
        '@app.post("/cascade/disable")',
    ):
        assert route in source
    assert 'active_page="cascade"' in source
    assert "configure_cascade(" in source


def test_routing_exposes_verified_cascade_actions():
    source = Path("app/web/templates/routing.html").read_text(encoding="utf-8")
    backend = Path("app/routing/templates.py").read_text(encoding="utf-8")
    assert "Каскад · IPv4" in source
    assert "Каскад · IPv6" in source
    assert "caps.get('cascade4')" in source
    assert "caps.get('cascade6')" in source
    assert '"cascade4"' in backend
    assert '"cascade6"' in backend
    assert "custom_cascade4_domains" in backend
    assert "custom_cascade6_domains" in backend
    assert "blocked_cascade" in source
    assert "all_cascade" in source
    assert '"blocked_cascade"' in backend
    assert '"all_cascade"' in backend

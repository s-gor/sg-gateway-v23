from __future__ import annotations

from pathlib import Path


def test_cascade_is_a_first_class_menu_section():
    base = Path("app/web/templates/base.html").read_text(encoding="utf-8")
    assert "url_for('cascade')" in base
    assert "<strong>Cascade</strong>" in base
    assert "SG-Gateway → SG-Gateway" in base
    assert base.index("url_for('outbounds')") < base.index("url_for('cascade')") < base.index('href="/routing"')


def test_cascade_page_uses_sg_ui_shell_and_real_state():
    source = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in source
    assert "SG-Gateway · Cascade" in source
    assert "SG-GATEWAY / CASCADE" in source
    assert "<h1>Cascade</h1>" in source
    assert "sg-ui-page" in source
    assert "sg-ui-section" in source
    assert "sg-ui-cascade-v23-02.css" in source
    assert "Клиент" in source
    assert "GATEWAY A" in source
    assert "GATEWAY B" in source
    assert "Интернет" in source
    assert "cascade.channels" in source
    assert "cascade.ready_count" in source
    assert "cascade.required_count" in source
    assert "cascade.ipv4_ready" in source
    assert "cascade.ipv6_ready" in source
    assert "cascade_test_all" in source
    assert "cascade_bundle_export" in source
    assert "cascade_import" in source
    assert "cascade_mode" in source
    assert "cascade_enable" in source
    assert "cascade_disable" in source
    assert "confirm(" not in source
    assert "alert(" not in source
    assert "prompt(" not in source


def test_cascade_page_does_not_echo_saved_secrets():
    source = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    assert "channel.payload" not in source
    assert "cascade.outbound" not in source
    assert "publicKey" not in source
    assert "shortId" not in source
    assert "password" not in source.lower()


def test_cascade_routes_are_present():
    source = Path("app/main.py").read_text(encoding="utf-8")
    for route in (
        '@app.get("/cascade")',
        '@app.get("/cascade/bundle")',
        '@app.post("/cascade/import")',
        '@app.post("/cascade/test-all")',
        '@app.post("/cascade/mode")',
        '@app.post("/cascade/enable")',
        '@app.post("/cascade/disable")',
    ):
        assert route in source
    assert 'active_page="cascade"' in source
    assert "import_cascade_bundle(" in source
    assert "test_all_cascade_channels(" in source


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


def test_cascade_dashboard_has_nine_real_channel_slots():
    source = Path("app/cascade/bundle.py").read_text(encoding="utf-8")
    template = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    for channel_id in (
        "reality_tcp",
        "xhttp_reality",
        "xhttp_tls",
        "hysteria2",
        "awg31",
        "mieru",
        "anytls",
        "tuic",
        "naiveproxy",
    ):
        assert f'("{channel_id}",' in source
    assert "for channel in cascade.channels" in template
    assert "Каскад можно включить только после успешной проверки всех девяти каналов" in template
    assert "Проверить все каналы" in template
    assert "Настроить приоритет" in template
    assert "Создать / скачать bundle" in template
    assert "СЕРВЕР ВАШИХ КЛИЕНТОВ" in template
    assert "ВЫХОДНОЙ СЕРВЕР" in template
    assert "К этому серверу подключаются ваши клиенты" in template
    assert "Название выходного сервера" in template


def test_cascade_uses_two_channel_cards_per_row_and_visual_priority():
    css = Path("app/web/static/sg-ui-cascade-v23-02.css").read_text(encoding="utf-8")
    template = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    js = Path("app/web/static/sg-cascade-v23-02.js").read_text(encoding="utf-8")

    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "body.page-cascade .cs-channel-grid" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "Порядок каналов" in template
    assert "data-cascade-priority-list" in template
    assert "data-cascade-priority-input" in template
    assert "data-priority-move" in template
    assert "sg-cascade-v23-02.js" in template
    assert "dragstart" in js
    assert "dragend" in js
    assert "data-priority-channel" in js


def test_cascade_priority_ui_hides_internal_ids_from_status_summary():
    template = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    assert "priority_names.get(item, item)" in template
    assert "Резервные каналы" in template
    assert "Идентификаторы каналов через запятую" not in template


def test_cascade_reuses_native_connections_visual_components():
    template = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    css = Path("app/web/static/sg-ui-cascade-v23-02.css").read_text(encoding="utf-8")

    for asset in (
        "sg-ui-connections-components-v22-08.css",
        "sg-xray-profiles-v2.css",
        "sg-ui-connections-v22-08.css",
    ):
        assert asset in template

    for klass in (
        "cnv1-heading",
        "cnv1-heading-actions",
        "cnv1-engine-card",
        "cnv1-engine-head",
        "cnv1-engine-title",
        "cnv1-engine-status",
        "cnv1-endpoint-card",
        "cnv1-endpoint-main",
        "cnv1-port-chip",
        "xps2-panel",
        "xps2-top-actions",
        "xps2-selection",
        "xps2-section-head",
        "xps2-choice-grid",
        "xps2-choice",
        "xps2-choice-topline",
        "xps2-choice-status",
        "xps2-parameters",
        "xps2-parameter-list",
        "xps2-parameter-row",
        "cnv1-compact-protocol-grid",
        "cnv1-compact-protocol-card",
        "cnv1-note-panel",
        "button primary",
    ):
        assert klass in template

    assert "cs-primary" not in template
    assert "cs-secondary" not in template
    assert "cs-board" not in template
    assert "cs-summary" not in template
    assert "cs-setup-grid" not in template
    assert "The page intentionally mirrors Connections" in css


def test_cascade_channel_card_markup_matches_connections_profile_cards():
    template = Path("app/web/templates/cascade.html").read_text(encoding="utf-8")
    start = template.index('<article class="xps2-choice cs-channel')
    sample = template[start:start + 1600]
    assert "xps2-choice-topline" in sample
    assert "<strong>{{ channel.title }}</strong>" in sample
    assert "<p>" in sample
    assert "xps2-choice-status" in sample
    assert "cs-channel-head" not in sample
    assert "cs-channel-icon" not in sample

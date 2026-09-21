from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_decorative_map_is_removed():
    template = (ROOT / "app/web/templates/connections.html").read_text(encoding="utf-8")
    assert "cnv1-map-panel" not in template
    assert "СХЕМА ПОДКЛЮЧЕНИЙ" not in template
    assert "Интернет → SG-Gateway → клиентский профиль" not in template




def test_connections_has_native_naiveproxy_panel_without_html_injection():
    template = (ROOT / "app/web/templates/connections.html").read_text(encoding="utf-8")
    panel = (ROOT / "app/web/templates/_naiveproxy_panel.html").read_text(encoding="utf-8")
    http = (ROOT / "app/naiveproxy/http.py").read_text(encoding="utf-8")

    assert template.count('{% include "_naiveproxy_panel.html" %}') == 1
    assert 'id="sg-naiveproxy-settings"' in panel
    assert 'data-naiveproxy-panel' in panel
    assert "/api/naiveproxy/status" in panel
    assert "/api/naiveproxy/settings" in panel
    assert "_SETTINGS_PANEL" not in http
    assert 'request.endpoint == "connections"' not in http


def test_naiveproxy_runtime_meta_row_is_not_rendered():
    panel = (ROOT / "app/web/templates/_naiveproxy_panel.html").read_text(encoding="utf-8")
    assert "xps2-naiveproxy-meta" not in panel
    assert "Состояние runtime" not in panel
    assert "data-naive-runtime" not in panel


def test_naiveproxy_has_no_internal_separators_and_is_compact():
    css = (ROOT / "app/web/static/sg-ui-connections-v22-08.css").read_text(encoding="utf-8")
    assert "body.page-connections .xps2-naiveproxy-card .cnv1-engine-head {" in css
    assert "padding: 15px 18px 12px;" in css

    body_selector = "body.page-connections .xps2-naiveproxy-body {"
    assert body_selector in css
    body = css.split(body_selector, 1)[1].split("}", 1)[0]
    assert "margin-top: 10px;" in body
    assert "border-top: 0;" in body
    assert "padding: 8px 18px 14px;" in body

    actions_selector = "body.page-connections .xps2-naiveproxy-body .cnv1-form-actions {"
    assert actions_selector in css
    actions = css.split(actions_selector, 1)[1].split("}", 1)[0]
    assert "border-top: 0;" in actions
    assert "padding-top: 0;" in actions


def test_awg_header_has_no_visual_divider():
    css = (ROOT / "app/web/static/sg-awg-dual-v1.css").read_text(encoding="utf-8")
    assert ".awgd-shell > .cnv1-engine-head { border-bottom:" not in css




def test_mihomo_is_compact_and_keeps_three_protocols():
    panel = (ROOT / "app/web/templates/_mihomo_panel.html").read_text(encoding="utf-8")
    assert "cnv1-engine-mihomo" in panel
    for protocol in ("Mieru", "AnyTLS", "TUIC v5"):
        assert protocol in panel
    for field in (
        'name="mieru_enabled"', 'name="anytls_enabled"', 'name="tuic_enabled"',
    ):
        assert field in panel
    assert 'name="mieru_transport"' not in panel
    for field in ("mieru_port", "anytls_port", "tuic_port"):
        assert f'name="{field}"' not in panel
    for value in (
        "{{ mihomo.settings.mieru_port }}",
        "{{ mihomo.settings.anytls_port }}",
        "{{ mihomo.settings.tuic_port }}",
    ):
        assert value not in panel
    assert "Системный порт SG-Gateway" not in panel
    assert "mhv2-compact-endpoint" not in panel
    assert "mhv2-summary" not in panel
    assert "mhv2-sgclient" not in panel


def test_green_cyan_button_outline_is_removed():
    css = (ROOT / "app/web/static/sg-preview28-final.css").read_text(encoding="utf-8")
    assert "border-color: transparent !important" in css
    assert ".sg-nav-item.active" in css
    assert ".mhv2-switch input:checked + span" in css
    assert "sg-preview28-final.css" in (ROOT / "app/web/templates/base.html").read_text(encoding="utf-8")


def test_connections_summary_cards_are_removed():
    template = (ROOT / "app/web/templates/connections.html").read_text(encoding="utf-8")
    assert 'class="cnv1-summary sg-ljd-strip"' not in template
    assert "cnv1-summary-card" not in template


def test_awg_and_mihomo_keep_equal_height_contract():
    css = (ROOT / "app/web/static/sg-preview28-final.css").read_text(encoding="utf-8")
    assert "height: auto; align-self: stretch;" in css
    assert ".cnv1-engine-awg .cnv1-engine-form-compact { flex: 1 1 auto; }" in css
    assert ".cnv1-engine-awg .cnv1-form-actions { margin-top: auto; }" in css

def test_xray_fingerprint_selector_uses_only_documented_public_presets():
    profiles = (ROOT / "app/xray/profiles.py").read_text(encoding="utf-8")
    template = (ROOT / "app/web/templates/connections.html").read_text(encoding="utf-8")

    expected = (
        "chrome", "firefox", "safari", "ios", "android",
        "edge", "360", "qq", "random", "randomized",
    )
    start = profiles.index("FINGERPRINT_VALUES = (")
    end = profiles.index(")\nFINGERPRINT_DEFAULT", start)
    block = profiles[start:end]
    for value in expected:
        assert f'"{value}"' in block
        assert f'value="{value}"' in template
    for removed in ("brave", "opera", "vivaldi", "unsafe"):
        assert f'"{removed}"' not in block
        assert f'value="{removed}"' not in template

    assert 'FINGERPRINT_DEFAULT = "chrome"' in profiles
    assert "<optgroup" not in template[template.index('name="fingerprint"'):template.index("</select>", template.index('name="fingerprint"'))]


def test_xray_fingerprint_dropdown_keeps_dark_native_popup():
    css = (ROOT / "app/web/static/sg-xray-primary-settings-v1.css").read_text(encoding="utf-8")
    assert 'html[data-theme="dark"] body.page-connections .xps2-primary-control > select {' in css
    assert "color-scheme: dark !important;" in css
    assert "background-color: var(--sg-panel-deep) !important;" in css
    assert 'html[data-theme="dark"] body.page-connections .xps2-primary-control > select > option {' in css


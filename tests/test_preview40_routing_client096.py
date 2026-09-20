from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_routing_layout_is_ported_from_sg_client_096():
    template = (ROOT / "app/web/templates/routing.html").read_text(encoding="utf-8")
    for marker in (
        "Выбранная конфигурация",
        "Пользовательские правила",
        "Базовая схема",
        "Основные правила",
        "Российская маршрутизация",
        "Наборы geosite / geoip",
    ):
        assert marker in template
    assert 'data-r096-tab="routing"' in template
    assert 'data-r096-tab="geofiles"' in template


def test_custom_routing_preset_opens_user_rules_editor():
    template = (ROOT / "app/web/templates/routing.html").read_text(encoding="utf-8")
    for marker in (
        "data-r096-user-rules",
        "data-r096-user-rules-toggle",
        "data-r096-user-rules-label",
        "event.preventDefault()",
        "userRules.open = !userRules.open",
        "input.value === 'custom' && input.checked",
        "userRules.open = true",
        "userRules.scrollIntoView",
    ):
        assert marker in template
    assert "{% if preset == 'custom' %}open{% endif %}" in template


def test_routing_themes_match_current_sg_gateway_palettes():
    css = (ROOT / "app/web/static/sg-routing-client096.css").read_text(encoding="utf-8")
    for color in (
        "#0B121C",
        "#111D2B",
        "#7FB2E0",
        "#477AAA",
        "#315E8C",
        "#E5ECE7",
        "#F8F5EE",
        "#456F5C",
        "#B88A45",
    ):
        assert color in css


def test_geofiles_ui_and_sources_are_complete():
    template = (ROOT / "app/web/templates/_geofiles_panel.html").read_text(encoding="utf-8")
    source = (ROOT / "app/routing/geofiles.py").read_text(encoding="utf-8")
    for marker in ("Установленные файлы", "Источник GeoFiles", "Проверка и применение", "Вернуть комплектные"):
        assert marker in template
    for source_name in ("Loyalsoldier", "RunetFreedom", "RoscomVPN", "Встроенная пара SG Client"):
        assert source_name in source
    assert (ROOT / "assets/geofiles/geoip.dat").stat().st_size > 1_000_000
    assert (ROOT / "assets/geofiles/geosite.dat").stat().st_size > 1_000_000


def test_smart_routing_backend_is_wired():
    templates = (ROOT / "app/routing/templates.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "def stage_smart_routing" in templates
    assert "SMART_PRESET_TITLES" in templates
    assert '@app.post("/routing/smart/preview")' in main


def test_smart_routing_builds_real_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_GATEWAY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SG_GATEWAY_LOG_DIR", str(tmp_path / "log"))
    monkeypatch.setenv("SG_GATEWAY_GEOFILES_STATE_DIR", str(tmp_path / "geo-state"))
    monkeypatch.setenv("SG_GATEWAY_XRAY_ASSET_DIR", str(ROOT / "assets/geofiles"))
    monkeypatch.setenv("SG_GATEWAY_ROUTING_STATE_DIR", str(tmp_path / "routing"))
    from app.db import init_db
    from app.routing.templates import stage_smart_routing
    init_db()
    candidate = stage_smart_routing(
        {
            "preset": "custom",
            "russia_scope": "sites_ip",
            "russia_action": "direct",
            "ads_action": "block",
            "default_action": "direct",
            "custom_direct_domains": "example.com",
            "custom_block_ips": "203.0.113.10",
        }
    )
    assert candidate["ready"] is True
    assert candidate["smart"]["preset"] == "custom"
    rules = candidate["managed_fragment"]["routing"]["rules"]
    assert rules
    assert {rule["outboundTag"] for rule in rules} <= {"direct", "block"}
    assert not any(rule.get("network") == "tcp,udp" for rule in rules)
    assert candidate["rules"][-1].get("implicit_default") is True
    assert any(rule["title"] == "Российская маршрутизация" for rule in candidate["rules"])



def test_custom_missing_optional_blocked_category_does_not_block_candidate(monkeypatch):
    from app.routing import templates

    monkeypatch.setattr(
        templates,
        "_available_categories",
        lambda: ({"private"}, {"private", "category-ads-all"}),
    )
    monkeypatch.setattr(
        templates,
        "routing_capabilities",
        lambda: {
            "direct4": True,
            "direct6": False,
            "warp4": False,
            "warp6": False,
            "block": True,
            "warp_enabled": False,
        },
    )
    state = templates._smart_default()
    state.update(
        preset="custom",
        local_action="direct4",
        blocked_action="block",
        ads_action="block",
        default_action="direct4",
    )

    candidate = templates._smart_build(state)

    assert candidate["ready"] is True
    blocked = next(
        rule for rule in candidate["rules"]
        if rule["title"] == "Ресурсы, заблокированные в РФ"
    )
    assert blocked["enabled"] is False
    assert blocked["required"] is False
    assert blocked["missing"] == ["geosite:ru-blocked"]
    managed = candidate["managed_fragment"]["routing"]["rules"]
    assert not any(rule.get("domain") == ["geosite:ru-blocked"] for rule in managed)
    assert "необязательное правило пропущено" in candidate["message"]


def test_ads_block_preset_requires_ads_category(monkeypatch):
    from app.routing import templates

    monkeypatch.setattr(
        templates,
        "_available_categories",
        lambda: ({"private"}, {"private"}),
    )
    monkeypatch.setattr(
        templates,
        "routing_capabilities",
        lambda: {
            "direct4": True,
            "direct6": False,
            "warp4": False,
            "warp6": False,
            "block": True,
            "warp_enabled": False,
        },
    )
    state = templates._smart_apply_preset(
        {**templates._smart_default(), "preset": "ads_block"}
    )

    candidate = templates._smart_build(state)

    assert candidate["ready"] is False
    ads = next(rule for rule in candidate["rules"] if rule["title"] == "Реклама и трекеры")
    assert ads["required"] is True
    assert ads["missing"] == ["geosite:category-ads"]


def test_routing_preview_labels_optional_missing_rule_as_skipped():
    template = (ROOT / "app/web/templates/routing.html").read_text(encoding="utf-8")
    css = (ROOT / "app/web/static/sg-routing-client096.css").read_text(encoding="utf-8")
    assert "Категория не найдена · правило пропущено" in template
    assert "Пропущено" in template
    assert "'skip' if optional_skipped" in template
    assert ".r096-rule-list .route-skip" in css



def test_privacy_preset_builds_available_protection_rules(monkeypatch):
    from app.routing import templates

    monkeypatch.setattr(
        templates,
        "_available_categories",
        lambda: (
            {"private"},
            {
                "private",
                "category-ads-all",
                "category-tracker",
                "category-malware",
                "category-phishing",
                "win-spy",
            },
        ),
    )
    monkeypatch.setattr(
        templates,
        "routing_capabilities",
        lambda: {
            "direct4": True,
            "direct6": False,
            "warp4": False,
            "warp6": False,
            "block": True,
            "warp_enabled": False,
        },
    )
    state = templates._smart_apply_preset(
        {**templates._smart_default(), "preset": "privacy"}
    )

    candidate = templates._smart_build(state)

    assert candidate["ready"] is True
    titles = {rule["title"] for rule in candidate["rules"] if rule["enabled"]}
    assert {
        "Реклама и трекеры",
        "Трекеры",
        "Вредоносные домены",
        "Фишинг",
        "Телеметрия",
    } <= titles
    blocked_domains = {
        domain
        for rule in candidate["managed_fragment"]["routing"]["rules"]
        if rule.get("outboundTag") == "block"
        for domain in rule.get("domain", [])
    }
    assert {
        "geosite:category-ads-all",
        "geosite:category-tracker",
        "geosite:category-malware",
        "geosite:category-phishing",
        "geosite:win-spy",
    } <= blocked_domains


def test_strict_adds_miners_and_skips_unavailable_optional_groups(monkeypatch):
    from app.routing import templates

    monkeypatch.setattr(
        templates,
        "_available_categories",
        lambda: (
            {"private"},
            {"private", "category-ads-all", "category-cryptominers"},
        ),
    )
    monkeypatch.setattr(
        templates,
        "routing_capabilities",
        lambda: {
            "direct4": True,
            "direct6": False,
            "warp4": False,
            "warp6": False,
            "block": True,
            "warp_enabled": False,
        },
    )
    state = templates._smart_apply_preset(
        {**templates._smart_default(), "preset": "strict"}
    )

    candidate = templates._smart_build(state)

    assert candidate["ready"] is True
    miners = next(rule for rule in candidate["rules"] if rule["title"] == "Криптомайнеры")
    assert miners["enabled"] is True
    assert miners["selected_geosite"] == "category-cryptominers"
    skipped = [
        rule for rule in candidate["rules"]
        if rule["title"] in {"Трекеры", "Вредоносные домены", "Фишинг", "Телеметрия"}
        and not rule["enabled"]
    ]
    assert len(skipped) == 4
    assert all(rule["required"] is False for rule in skipped)


def test_privacy_and_strict_are_visible_in_routing_ui():
    template = (ROOT / "app/web/templates/routing.html").read_text(encoding="utf-8")
    assert "Privacy · реклама + трекеры + угрозы" in template
    assert "Strict · усиленная фильтрация" in template

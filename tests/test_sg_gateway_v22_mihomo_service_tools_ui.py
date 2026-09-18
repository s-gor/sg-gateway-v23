from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/web/templates/_mihomo_panel.html"


def test_mihomo_restart_is_visible_in_primary_action_row() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert 'class="mhv2-service-tools"' not in source
    assert "Сервисные действия" not in source
    assert "<summary>Перезапуск" not in source
    assert 'class="mhv2-restart-row"' not in source
    assert "Перезапустить Mihomo" not in source

    actions = source.split('<div class="mhv2-actions">', 1)[1].split("</div>", 1)[0]
    for value in ("save", "test", "apply", "restart"):
        assert f'name="action" value="{value}"' in actions
    assert actions.index('value="save"') < actions.index('value="test"')
    assert actions.index('value="test"') < actions.index('value="apply"')
    assert actions.index('value="apply"') < actions.index('value="restart"')
    assert 'value="restart">Перезапустить</button>' in actions
    assert '<span class="mhv2-restart-note">Только для уже применённой конфигурации.</span>' in actions


def test_mihomo_listener_runtime_statuses_are_preserved_without_aggregate_counter() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert source.count("data-runtime-switch") >= 3
    assert "mieru_state.state_label" in source
    assert "anytls_state.state_label" in source
    assert "tuic_state.state_label" in source
    assert "mihomo.listener_active" not in source
    assert "mihomo.listener_total" not in source


def test_mihomo_compact_spacing_contract() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "#mihomo .mhv2-compact-meta" in source
    assert "gap: 8px;" in source
    assert "margin-bottom: 6px;" in source
    assert "#mihomo .mhv2-form-compact" in source
    assert "gap: 10px;" in source
    assert "#mihomo .mhv2-actions" in source
    action_css = source.split("#mihomo .mhv2-actions {", 1)[1].split("}", 1)[0]
    assert "align-items: center;" in action_css
    assert "flex-wrap: wrap;" in action_css
    assert "justify-content: center;" in action_css


def test_mieru_user_hint_checkbox_stays_compact() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert '#mihomo .mhv2-check input[type="checkbox"] {' in source
    assert 'width: 16px !important;' in source
    assert 'height: 16px !important;' in source
    assert 'min-width: 16px !important;' in source
    assert 'min-height: 16px !important;' in source


def test_runtime_status_copy_is_hidden_to_keep_cards_compact() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert '#mihomo .sg-runtime-copy small {' in source
    assert 'display: none !important;' in source


def test_mihomo_pending_guidance_is_compact_and_actionable() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "Рабочие listener и клиентские ссылки изменятся только после кнопки" not in source
    assert "Mieru обслуживается Mihomo." not in source
    assert "Ошибка дополнительного движка" not in source
    assert "Подключите клиента" in source
    assert "Выключено" in source


def test_aggregate_pending_banner_is_removed() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "Есть неприменённые изменения" not in source
    assert "mihomo.has_pending_changes" not in source

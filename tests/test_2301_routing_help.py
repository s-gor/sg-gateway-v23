from pathlib import Path

from app.help.content import get_topic


ROOT = Path(__file__).resolve().parents[1]


def test_embedded_help_has_detailed_outbounds_and_routing_topics():
    outbounds = get_topic("outbounds")
    routing = get_topic("routing")

    assert outbounds is not None
    assert routing is not None
    assert len(outbounds.body) >= 8
    assert len(routing.body) >= 10

    outbounds_text = " ".join(outbounds.body)
    routing_text = " ".join(routing.body)

    for marker in ("SOCKS5", "HTTP CONNECT", "Round Robin", "Random", "Failover", "Observatory", "fallbackTag"):
        assert marker in outbounds_text

    for marker in (
        "Фактические правила candidate",
        "Проверить",
        "Применить",
        "IPv4",
        "IPv6",
        "GeoFiles",
        "Остальной трафик",
        "первое совпадение",
    ):
        assert marker in routing_text


def test_routing_manual_covers_complete_operator_workflow():
    manual = (ROOT / "docs" / "ROUTING.md").read_text(encoding="utf-8")

    for heading in (
        "## 1. Самый простой сценарий",
        "## 2. Базовые схемы",
        "## 3. Основные правила",
        "## 4. Порядок правил",
        "## 5. Пользовательские правила",
        "## 6. Как добавить внешний сервер",
        "## 7. Outbound Groups",
        "## 8. Практические примеры",
        "## 9. WARP",
        "## 10. IPv4 и IPv6",
        "## 11. GeoFiles",
        "## 12. Проверить → Применить",
        "## 14. Удаление внешнего outbound или группы",
        "## 15. Как проверить, что маршрут реально работает",
        "## 16. Типовые ошибки",
    ):
        assert heading in manual

    for marker in (
        "SOCKS5",
        "HTTP CONNECT",
        "Round Robin",
        "Random",
        "Failover",
        "Xray Observatory",
        "Остальной трафик",
        "Фактические правила candidate",
        "изменить → Проверить → Применить",
    ):
        assert marker in manual


def test_user_guide_points_to_full_routing_manual():
    guide = (ROOT / "docs" / "USER-GUIDE.md").read_text(encoding="utf-8")
    assert "внешние SOCKS5 и HTTP CONNECT" in guide
    assert "Round Robin" in guide
    assert "Failover" in guide
    assert "[Routing, Outbounds и GeoFiles](ROUTING.md)" in guide


def test_help_template_has_outbounds_navigation():
    template = (ROOT / "app" / "web" / "templates" / "help.html").read_text(encoding="utf-8")
    assert "topic.slug in ['routing', 'outbounds']" in template
    assert "url_for('outbounds')" in template
    assert "WARP, внешние proxy, группы и Failover" in template

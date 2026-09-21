from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mihomo_service_allows_netlink_route_lookup():
    unit = (ROOT / "deploy" / "mihomo.service").read_text(encoding="utf-8")
    line = next(
        item.strip()
        for item in unit.splitlines()
        if item.startswith("RestrictAddressFamilies=")
    )
    families = set(line.partition("=")[2].split())
    assert {"AF_UNIX", "AF_INET", "AF_INET6", "AF_NETLINK"} <= families


def test_update_refreshes_and_rolls_back_mihomo_unit():
    source = (ROOT / "deploy" / "update-from-github-core.sh").read_text(
        encoding="utf-8"
    )
    assert 'MIHOMO_UNIT="$(system_path /etc/systemd/system/mihomo.service)"' in source
    assert "etc/systemd/system/mihomo.service" in source
    assert '"$MIHOMO_UNIT"' in source
    assert "sync_mihomo_service_unit()" in source
    assert 'install -m 0644 "$source" "$MIHOMO_UNIT"' in source
    assert "systemctl restart mihomo.service" in source
    assert (
        'run_stage 5 "Перезапуск panel + hostd и синхронизация Mihomo unit" '
        "restart_panel_and_sync_mihomo"
    ) in source

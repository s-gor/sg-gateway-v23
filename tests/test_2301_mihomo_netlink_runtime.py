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


def test_clean_install_installs_managed_mihomo_unit():
    install = (ROOT / "deploy" / "install-core.sh").read_text(encoding="utf-8")
    assert (
        'install -m 0644 "$PREFIX/deploy/mihomo.service" '
        "/etc/systemd/system/mihomo.service"
    ) in install

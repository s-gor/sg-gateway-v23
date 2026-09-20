from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "install-from-github.sh"


def _installer_source() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_clean_install_waits_for_cloud_init_before_disk_and_apt_work() -> None:
    source = _installer_source()

    assert "cloud-init status --wait" in source
    assert source.index("wait_for_cloud_init") < source.index(
        'require_free_space /opt "installation and temporary storage"'
    )


def test_clean_install_refreshes_package_index_before_downloading_gateway_source() -> None:
    source = _installer_source()

    assert "apt-get -o Dpkg::Use-Pty=0 update" in source
    assert 'FULL_OS_UPGRADE="${SG_GATEWAY_FULL_OS_UPGRADE:-0}"' in source
    assert 'if [[ "$FULL_OS_UPGRADE" == "1" ]]' in source
    assert "full-upgrade -y" in source
    assert "autoremove -y" in source
    assert source.index('if [[ "$FULL_OS_UPGRADE" == "1" ]]') < source.index(
        "full-upgrade -y"
    )
    assert source.index("prepare_clean_ubuntu") < source.index(
        "Downloading GitHub branch"
    )


def test_clean_install_passes_prepared_apt_index_to_native_installer() -> None:
    source = _installer_source()
    native = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "SG_GATEWAY_APT_INDEX_READY=1" in source
    assert 'if [[ "${SG_GATEWAY_APT_INDEX_READY:-0}" == "1" ]]' in native


def test_reboot_required_stops_before_gateway_install_without_rebooting() -> None:
    source = _installer_source()

    assert "/var/run/reboot-required" in source
    assert "repeat the same SG-Gateway install command" in source
    assert "systemctl reboot" not in source
    assert "shutdown -r" not in source


def test_clean_install_bootstrap_uses_quiet_green_progress_contract() -> None:
    source = _installer_source()

    assert 'BOOTSTRAP_LOG="/var/log/sg-gateway-bootstrap-02301.log"' in source
    assert "run_quiet()" in source
    assert "local frames=('|' '/' '-' \"\\\\\")" in source
    assert "\\033[1;32m" in source
    assert 'run_quiet "Подготовка 1/6 · Проверка Ubuntu" require_supported_ubuntu' in source
    assert 'run_quiet "Подготовка 2/6 · Ожидание cloud-init" wait_for_cloud_init' in source
    assert 'run_quiet "Подготовка 3/6 · Проверка диска" preflight_disk_space' in source
    assert 'run_quiet "Подготовка 4/6 · Индекс пакетов Ubuntu" prepare_clean_ubuntu' in source
    assert 'run_quiet "Подготовка 5/6 · Подготовка инструментов" prepare_bootstrap_tools' in source
    assert 'run_quiet "Подготовка 6/6 · Загрузка SG-Gateway" download_gateway_source' in source


def test_clean_install_bootstrap_hides_raw_output_but_keeps_failure_log() -> None:
    source = _installer_source()

    assert 'if [[ -t 1 ]]' in source
    assert '>"$raw_output" 2>&1 &' in source
    assert 'cat "$raw_output" >> "$BOOTSTRAP_LOG"' in source
    assert 'Полный технический журнал: %s\\n' in source
    assert '"$BOOTSTRAP_LOG"' in source


def test_clean_install_accepts_any_ubuntu_version() -> None:
    source = _installer_source()

    assert '[[ "${ID:-}" == "ubuntu" ]]' in source
    assert 'VERSION_ID' not in source
    assert 'only Ubuntu 24.04 is supported' not in source


def test_clean_install_uses_dedicated_bootstrap_temp_root() -> None:
    source = _installer_source()

    assert 'BOOTSTRAP_TMP_ROOT="/opt/sg-gateway-bootstrap-tmp"' in source
    assert 'install -d -m 0711 "$BOOTSTRAP_TMP_ROOT"' in source
    assert 'mktemp -d "$BOOTSTRAP_TMP_ROOT/sg-gateway-github-install.XXXXXX"' in source
    assert 'SG_GATEWAY_INSTALL_TMPDIR="$BOOTSTRAP_TMP_ROOT"' in source
    assert 'TMPDIR="$BOOTSTRAP_TMP_ROOT"' in source
    assert 'require_free_space /tmp' not in source


def test_native_installers_use_dedicated_temp_root() -> None:
    native = (ROOT / "install.sh").read_text(encoding="utf-8")
    core = (ROOT / "deploy" / "install-core.sh").read_text(encoding="utf-8")

    for source in (native, core):
        assert 'INSTALL_TMP_ROOT="${SG_GATEWAY_INSTALL_TMPDIR:-/opt/sg-gateway-bootstrap-tmp}"' in source
        assert 'install -d -m 0711 "$INSTALL_TMP_ROOT"' in source
        assert 'export TMPDIR="$INSTALL_TMP_ROOT"' in source
        assert "/tmp/sg-gateway-" not in source
        assert "VERSION_ID" not in source


def test_dedicated_temp_root_is_traversable_by_service_user() -> None:
    wrapper = _installer_source()
    native = (ROOT / "install.sh").read_text(encoding="utf-8")
    core = (ROOT / "deploy" / "install-core.sh").read_text(encoding="utf-8")

    assert 'install -d -m 0711 "$BOOTSTRAP_TMP_ROOT"' in wrapper
    for source in (native, core):
        assert 'install -d -m 0711 "$INSTALL_TMP_ROOT"' in source
        assert 'chown "$PANEL_USER":"$PANEL_GROUP" "$import_test_root"' in source
        assert 'install -d -o "$PANEL_USER" -g "$PANEL_GROUP" -m 0750' in source

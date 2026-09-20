from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "install-from-github.sh"


def _installer_source() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_clean_install_waits_for_cloud_init_before_disk_and_apt_work() -> None:
    source = _installer_source()

    assert "cloud-init status --wait" in source
    assert source.index("wait_for_cloud_init") < source.index(
        'require_free_space /tmp "temporary storage"'
    )


def test_clean_install_updates_ubuntu_before_downloading_gateway_source() -> None:
    source = _installer_source()

    assert "full-upgrade -y" in source
    assert "autoremove -y" in source
    assert source.index("prepare_clean_ubuntu") < source.index(
        "Downloading GitHub branch"
    )


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
    assert 'run_quiet "Подготовка 4/6 · Обновление Ubuntu" prepare_clean_ubuntu' in source
    assert 'run_quiet "Подготовка 5/6 · Подготовка инструментов" prepare_bootstrap_tools' in source
    assert 'run_quiet "Подготовка 6/6 · Загрузка SG-Gateway" download_gateway_source' in source


def test_clean_install_bootstrap_hides_raw_output_but_keeps_failure_log() -> None:
    source = _installer_source()

    assert 'if [[ -t 1 ]]' in source
    assert '>"$raw_output" 2>&1 &' in source
    assert 'cat "$raw_output" >> "$BOOTSTRAP_LOG"' in source
    assert 'Полный технический журнал: %s\\n' in source
    assert '"$BOOTSTRAP_LOG"' in source

def test_clean_install_supports_ubuntu_2404_and_2604_only() -> None:
    bootstrap = _installer_source()
    core = (ROOT / "deploy" / "install-core.sh").read_text(encoding="utf-8")

    assert '[[ "${VERSION_ID:-}" == "24.04" || "${VERSION_ID:-}" == "26.04" ]]' in bootstrap
    assert 'only Ubuntu 24.04 and 26.04 are supported' in bootstrap
    assert '[[ "${VERSION_ID:-}" != "24.04" && "${VERSION_ID:-}" != "26.04" ]]' in core
    assert 'Поддерживаются Ubuntu 24.04 и 26.04' in core

def test_clean_install_does_not_require_large_tmp_on_azure_style_images() -> None:
    source = _installer_source()

    assert 'require_free_space /tmp "temporary storage"' not in source
    assert 'for candidate in /var/tmp /opt; do' in source
    assert 'BOOTSTRAP_TEMP_ROOT="$candidate"' in source
    assert 'require_free_space "$BOOTSTRAP_TEMP_ROOT" "temporary storage"' in source
    assert 'mktemp -d "$BOOTSTRAP_TEMP_ROOT/sg-gateway-github-install.XXXXXX"' in source


def test_clean_install_reselects_large_temp_storage_after_ubuntu_upgrade() -> None:
    source = _installer_source()

    assert source.count("select_bootstrap_temp_root") >= 3
    assert 'temporary storage after Ubuntu update' in source


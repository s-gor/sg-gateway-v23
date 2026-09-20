from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "install-from-github.sh"


def test_clean_installer_checks_free_space_before_download_and_extraction():
    text = INSTALLER.read_text(encoding="utf-8")

    assert 'MIN_FREE_MIB="${SG_GATEWAY_INSTALL_MIN_FREE_MIB:-1024}"' in text
    assert "require_free_space()" in text
    assert 'df -Pk "$path"' in text
    assert 'select_bootstrap_temp_root' in text
    assert 'require_free_space "$BOOTSTRAP_TEMP_ROOT" "temporary storage"' in text
    assert 'require_free_space /opt "installation storage"' in text
    assert "not enough free disk space for clean install" in text

    first_preflight = text.index('run_quiet "Подготовка 3/6 · Проверка диска" preflight_disk_space')
    package_bootstrap = text.index('run_quiet "Подготовка 5/6 · Подготовка инструментов" prepare_bootstrap_tools')
    download_stage = text.index('run_quiet "Подготовка 6/6 · Загрузка SG-Gateway" download_gateway_source')

    assert first_preflight < package_bootstrap < download_stage
    assert "Downloading GitHub branch" in text
    assert 'tar -xzf "$ARCHIVE"' in text

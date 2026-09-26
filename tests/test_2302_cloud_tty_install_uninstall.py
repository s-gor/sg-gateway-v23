from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_installer_supports_password_file_for_cloud_ssh():
    source = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'SG_GATEWAY_ADMIN_PASSWORD_FILE' in source
    assert 'Пароль администратора получен из защищённого файла.' in source
    assert 'hash_admin_password "$first"' in source


def test_full_uninstaller_supports_noninteractive_confirmation():
    source = (ROOT / "deploy" / "full-uninstall-ubuntu.sh").read_text(encoding="utf-8")
    assert 'SG_GATEWAY_UNINSTALL_CONFIRM' in source
    assert '[[ "$CONFIRM" != "DELETE SG-GATEWAY" ]]' in source
    assert 'SG_GATEWAY_UNINSTALL_CONFIRM="DELETE SG-GATEWAY"' in source


def test_feature_uninstall_wrapper_can_remove_feature_install():
    source = (ROOT / "deploy" / "uninstall-from-github.sh").read_text(encoding="utf-8")
    assert 'stable-02301|feature/2302-cascade' in source


def test_github_install_wrapper_reattaches_native_installer_to_tty():
    source = (ROOT / "deploy" / "install-from-github.sh").read_text(encoding="utf-8")
    assert 'bash "$SOURCE_DIR/install.sh" < /dev/tty' in source


def test_github_uninstall_wrapper_reattaches_native_uninstaller_to_tty():
    source = (ROOT / "deploy" / "uninstall-from-github.sh").read_text(encoding="utf-8")
    assert 'bash "$UNINSTALLER" < /dev/tty' in source

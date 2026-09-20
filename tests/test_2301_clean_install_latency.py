from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def _function(source: str, name: str) -> str:
    marker = f"{name}() {{"
    start = source.index(marker)
    end = source.index("\n}", start) + 2
    return source[start:end]


def test_2301_clean_install_verifies_vendor_bundle_once_in_main_flow() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert "stage_vendor_media_contract() {\n  verify_vendor_core_set\n}" in source
    assert "verify_vendor_core_set" not in _function(source, "stage_prepare_install_context")
    assert "verify_vendor_core_set" not in _function(source, "stage_xray_runtime")
    assert "verify_vendor_core_set" not in _function(source, "stage_mihomo_runtime")
    assert "verify_vendor_core_set" not in _function(source, "stage_singbox_and_warp_runtime")


def test_2301_clean_install_does_not_repeat_package_index_or_xz_install() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    bootstrap = _function(source, "bootstrap_packages")
    system_packages = _function(source, "stage_system_packages")
    compatibility = _function(source, "stage_system_packages_02208")

    assert 'SG_GATEWAY_APT_INDEX_READY:-0' in bootstrap
    assert "xz-utils" in system_packages
    assert "apt_get install -y xz-utils" not in compatibility

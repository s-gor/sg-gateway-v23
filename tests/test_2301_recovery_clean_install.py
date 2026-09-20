from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_recovery_clean_install_requires_exact_sha_for_non_default_branch():
    installer = (ROOT / "deploy/install-from-github.sh").read_text(encoding="utf-8")
    assert 'SG_GATEWAY_SOURCE_COMMIT must be a lowercase 40-character commit SHA' in installer
    assert 'non-default development branch requires SG_GATEWAY_SOURCE_COMMIT' in installer
    assert 'development installer is pinned to dev-02301' not in installer


def test_recovery_clean_install_uses_generic_archive_and_actual_channel():
    installer = (ROOT / "deploy/install-from-github.sh").read_text(encoding="utf-8")
    assert 'ARCHIVE="$TEMP_DIR/sg-gateway-source.tar.gz"' in installer
    assert "printf '[SG-Gateway] DEV channel: %s\\n' \"$BRANCH\"" in installer

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_feature_clean_installer_allows_exact_sha_pin():
    source = (ROOT / "deploy/install-from-github.sh").read_text(encoding="utf-8")
    assert 'if [[ "$BRANCH" != "dev-02301" && -z "$SOURCE_COMMIT" ]]' in source
    assert 'non-default development branch requires SG_GATEWAY_SOURCE_COMMIT' in source
    assert '[[ "$BRANCH" == "dev-02301" ]] || fail' not in source


def test_feature_clean_installer_reports_actual_channel():
    source = (ROOT / "deploy/install-from-github.sh").read_text(encoding="utf-8")
    assert "DEV channel: %s" in source
    assert '"$BRANCH"' in source
    assert "sg-gateway-source.tar.gz" in source

from pathlib import Path


def test_2301_version_identity():
    assert Path("VERSION").read_text().strip() == "0.1.0-023.01"
    assert Path("DEVELOPMENT-VERSION").read_text().strip() == "0.1.0-023.01-dev"
    assert Path("BUILD-ID").read_text().strip() == "MAIN-02301-DEV"


def test_active_commands_use_v23_only():
    paths = [
        Path("README.md"),
        Path("deploy/GITHUB-COMMANDS.md"),
        Path("deploy/install-from-github.sh"),
        Path("deploy/update-from-github.sh"),
        Path("deploy/update-from-github-core.sh"),
        Path("deploy/uninstall-from-github.sh"),
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "s-gor/sg-gateway-v23" in text
    assert "s-gor/sg-gateway-v22" not in text
    assert "stable-02208" not in text
    assert "6d8b07125289566a6e8a7ba206094d8969e92125" not in text

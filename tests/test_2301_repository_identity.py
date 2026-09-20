from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_2301_version_identity():
    assert (ROOT / "VERSION").read_text().strip() == "0.1.0-023.01"
    assert (ROOT / "DEVELOPMENT-VERSION").read_text().strip() == "0.1.0-023.01"
    assert (ROOT / "BUILD-ID").read_text().strip() == "STABLE-02301"


def test_active_commands_use_v23_only():
    paths = [
        ROOT / "README.md",
        ROOT / "deploy/GITHUB-COMMANDS.md",
        ROOT / "deploy/install-from-github.sh",
        ROOT / "deploy/update-from-github.sh",
        ROOT / "deploy/update-from-github-core.sh",
        ROOT / "deploy/uninstall-from-github.sh",
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "s-gor/sg-gateway-v23" in text
    assert "s-gor/sg-gateway-v22" not in text
    assert "stable-02208" not in text
    assert "6d8b07125289566a6e8a7ba206094d8969e92125" not in text


def test_active_commands_use_2301_repository_and_channel():
    for rel in (
        "deploy/install-from-github.sh",
        "deploy/update-from-github.sh",
        "deploy/uninstall-from-github.sh",
        "deploy/GITHUB-COMMANDS.md",
    ):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert "s-gor/sg-gateway-v23" in body
        assert "stable-02301" in body
        assert "s-gor/sg-gateway-v22" not in body
        assert "stable-02208" not in body


def test_readme_publishes_only_2301_current_identity_and_stable_install():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "0.1.0-023.01" in readme
    assert "23.01" in readme
    assert "stable-02301/deploy/install-from-github.sh" in readme
    assert "SG_GATEWAY_GITHUB_BRANCH=stable-02301" in readme
    assert "SG_GATEWAY_SOURCE_COMMIT=" not in readme
    assert "0.1.0-022.08" not in readme
    assert "status-022.08" not in readme
    assert "PUBLICATION-02208.md" not in readme

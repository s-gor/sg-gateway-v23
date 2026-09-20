from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_public_github_commands_are_published_for_2301_stable():
    body = (ROOT / "deploy/GITHUB-COMMANDS.md").read_text(encoding="utf-8")
    assert "s-gor/sg-gateway-v23" in body
    assert body.count("stable-02301") >= 6
    assert "sg-gateway-v22" not in body
    assert "stable-02208" not in body

def test_public_wrappers_target_2301_repository_and_channel():
    for rel in ("deploy/install-from-github.sh", "deploy/update-from-github.sh", "deploy/uninstall-from-github.sh"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert 'REPOSITORY="s-gor/sg-gateway-v23"' in body
        assert "stable-02301" in body
        assert "sg-gateway-v22" not in body
        assert "stable-02208" not in body

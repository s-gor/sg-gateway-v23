from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_password_prompt_uses_explicit_tty_state_in_both_installers() -> None:
    for relative in ("install.sh", "deploy/install-core.sh"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "read_password_secret()" in source
        assert "exec 9<>/dev/tty" in source
        assert 'tty_state="$(stty -g <&9)"' in source
        assert "stty -echo <&9" in source
        assert "IFS= read -r secret <&9" in source
        assert 'stty "$tty_state" <&9' in source
        assert 'read -r -s -t "$timeout_seconds"' not in source


def test_password_prompt_still_requires_confirmation_and_minimum_length() -> None:
    source = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'read_password_secret "[SG-Gateway] Пароль администратора (не менее 8 символов): " first' in source
    assert 'read_password_secret "[SG-Gateway] Повторите пароль: " second' in source
    assert 'if (( ${#first} < 8 )); then' in source
    assert 'if [[ "$first" != "$second" ]]; then' in source

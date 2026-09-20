from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hostd_client_apply_lock_lives_in_writable_state_dir() -> None:
    runtime = (ROOT / "hostd" / "sg_hostd" / "client_runtime.py").read_text(encoding="utf-8")
    assert 'LOCK_FILE = CANDIDATE_DIR / "clients-apply.lock"' in runtime
    assert '/run/sg-gateway/clients-apply.lock' not in runtime


def test_vendor_verification_is_quiet_and_installer_message_is_vm_neutral() -> None:
    for rel in ("install.sh", "deploy/install-core.sh"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert '(cd "$VENDOR_CORES_DIR" && sha256sum -c --quiet SHA256SUMS)' in text
        assert 'Этот же EC2 можно использовать повторно' not in text

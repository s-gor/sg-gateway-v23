from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "app" / "naiveproxy" / "integration.py"


def test_naiveproxy_runtime_wrapper_preserves_stabilize_keyword() -> None:
    source = INTEGRATION.read_text(encoding="utf-8")

    assert "def apply_clients_runtime(*, stabilize: bool = False) -> dict:" in source
    assert "if stabilize:" in source\n    assert "return original(stabilize=True)" in source\n    assert "return original()" in source

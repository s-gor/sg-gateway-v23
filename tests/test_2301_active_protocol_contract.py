import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_2301_active_awg_contract_is_awg31_only() -> None:
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["clients_ui"]["awg_generations"] == ["AWG3.1"]
    assert "awg2_awg3_independent_selection" not in manifest["client_access_model"]
    installer_update = manifest["installer_update"]
    assert "awg2_runtime_line" not in installer_update
    assert "awg3_runtime_line" not in installer_update

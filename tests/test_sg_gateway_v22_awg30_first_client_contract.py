from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_awg30_is_not_supported_for_new_client_credentials() -> None:
    repository = (ROOT / "app/clients/repository.py").read_text(encoding="utf-8")
    retirement = (ROOT / "app/clients/retired_awg.py").read_text(encoding="utf-8")

    assert 'RETIRED_ENGINES = frozenset({"amneziawg", "amneziawg3"})' in retirement
    assert "repository.SUPPORTED_ENGINES = tuple(" in retirement
    assert "repository.RUNTIME_ENGINES = tuple(" in retirement
    assert "amneziawg31" in repository


def test_awg30_and_awg31_historical_units_keep_separate_runtime_contracts() -> None:
    awg30 = (ROOT / "deploy/sg-gateway-awg3.service").read_text(encoding="utf-8")
    awg31 = (ROOT / "deploy/sg-gateway-awg31.service").read_text(encoding="utf-8")

    for unit in (awg30, awg31):
        assert "Type=simple" in unit
        assert "Environment=WG_PROCESS_FOREGROUND=1" in unit
        assert "RuntimeDirectory=amneziawg" in unit
        assert "RuntimeDirectoryPreserve=yes" in unit



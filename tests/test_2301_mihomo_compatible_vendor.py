from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPATIBLE = "mihomo-linux-amd64-compatible-v1.19.29.gz"
LEGACY = "mihomo-linux-amd64-v1.19.29.gz"
EXPECTED_SHA256 = "5612e698e96c8b8ad15abc4c0a4f098eba9234354b4f248cb97f2528e215b094"


def test_2301_installers_pin_mihomo_compatible_build() -> None:
    for relative in ("install.sh", "deploy/install-core.sh"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert f'MIHOMO_VENDOR_FILE="{COMPATIBLE}"' in text
        assert LEGACY not in text


def test_2301_vendor_bundle_contains_verified_mihomo_compatible_build() -> None:
    vendor = ROOT / "vendor" / "cores"
    asset = vendor / COMPATIBLE
    legacy = vendor / LEGACY
    manifest = (vendor / "SHA256SUMS").read_text(encoding="utf-8")

    assert asset.is_file()
    assert not legacy.exists()
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert f"{EXPECTED_SHA256}  {COMPATIBLE}" in manifest
    assert LEGACY not in manifest

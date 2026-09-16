from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Literal

Protocol = Literal["awg31", "hysteria2", "tuic"]


@dataclass(frozen=True)
class EdgeClassifierConfig:
    awg_enabled: bool = False
    awg_header_key: bytes = b""
    awg_s1: int = 0
    awg_h1_low: int = 0
    awg_h1_high: int = 0
    awg_s4: int = 0
    awg_h4_low: int = 0
    awg_h4_high: int = 0
    awg_random_trailers: bool = False
    hysteria_enabled: bool = False
    hysteria_mode: str = "none"
    hysteria_password: bytes = b""
    tuic_enabled: bool = False


def _rotl32(value: int, shift: int) -> int:
    return ((value << shift) & 0xFFFFFFFF) | (value >> (32 - shift))


def _quarter(state: list[int], a: int, b: int, c: int, d: int) -> None:
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF; state[d] ^= state[a]; state[d] = _rotl32(state[d], 16)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF; state[b] ^= state[c]; state[b] = _rotl32(state[b], 12)
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF; state[d] ^= state[a]; state[d] = _rotl32(state[d], 8)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF; state[b] ^= state[c]; state[b] = _rotl32(state[b], 7)


def _chacha20_prefix(key: bytes, nonce: bytes) -> bytes:
    if len(key) != 32 or len(nonce) != 12:
        return b""
    constants = b"expand 32-byte k"
    words = [int.from_bytes(constants[i:i+4], "little") for i in range(0, 16, 4)]
    words += [int.from_bytes(key[i:i+4], "little") for i in range(0, 32, 4)]
    words += [0]
    words += [int.from_bytes(nonce[i:i+4], "little") for i in range(0, 12, 4)]
    work = words[:]
    for _ in range(10):
        _quarter(work, 0, 4, 8, 12); _quarter(work, 1, 5, 9, 13); _quarter(work, 2, 6, 10, 14); _quarter(work, 3, 7, 11, 15)
        _quarter(work, 0, 5, 10, 15); _quarter(work, 1, 6, 11, 12); _quarter(work, 2, 7, 8, 13); _quarter(work, 3, 4, 9, 14)
    block = b"".join(((work[i] + words[i]) & 0xFFFFFFFF).to_bytes(4, "little") for i in range(16))
    return block[:4]


def decode_header_key(value: str) -> bytes:
    raw = str(value or "").strip()
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError):
        return b""
    return decoded if len(decoded) == 32 else b""


def parse_range(value: object) -> tuple[int, int]:
    text = str(value or "0").strip()
    left, sep, right = text.partition("-")
    try:
        low = int(left)
        high = int(right) if sep else low
    except ValueError:
        return (0, 0)
    return (low, high) if 0 <= low <= high <= 0xFFFFFFFF else (0, 0)


def _awg_header_matches(data: bytes, *, padding: int, low: int, high: int, minimum: int, exact: int | None, random_trailers: bool, key: bytes) -> bool:
    if padding < 12 or len(data) < padding + 4 or len(key) != 32:
        return False
    body_len = len(data) - padding
    if body_len < minimum:
        return False
    if exact is not None and not random_trailers and body_len != exact:
        return False
    stream = _chacha20_prefix(key, data[:12])
    if len(stream) != 4:
        return False
    header = bytes(a ^ b for a, b in zip(data[padding:padding+4], stream))
    value = int.from_bytes(header, "little")
    return low <= value <= high


def looks_like_awg31(data: bytes, config: EdgeClassifierConfig) -> bool:
    if not config.awg_enabled or len(config.awg_header_key) != 32:
        return False
    return _awg_header_matches(
        data, padding=config.awg_s1, low=config.awg_h1_low, high=config.awg_h1_high,
        minimum=148, exact=148, random_trailers=config.awg_random_trailers, key=config.awg_header_key,
    ) or _awg_header_matches(
        data, padding=config.awg_s4, low=config.awg_h4_low, high=config.awg_h4_high,
        minimum=16, exact=None, random_trailers=True, key=config.awg_header_key,
    )


def looks_like_quic_long_header(data: bytes) -> bool:
    if len(data) < 7 or (data[0] & 0xC0) != 0xC0:
        return False
    if int.from_bytes(data[1:5], "big") == 0:
        return False
    dcid_len = data[5]
    if dcid_len > 20 or len(data) < 6 + dcid_len + 1:
        return False
    scid_pos = 6 + dcid_len
    scid_len = data[scid_pos]
    return scid_len <= 20 and len(data) >= scid_pos + 1 + scid_len


def _salamander_plain(data: bytes, password: bytes) -> bytes:
    if len(data) <= 8 or not password:
        return b""
    salt, payload = data[:8], data[8:]
    mask = hashlib.blake2b(password + salt, digest_size=32).digest()
    return bytes(value ^ mask[index % 32] for index, value in enumerate(payload))


def looks_like_gecko_frame(data: bytes) -> bool:
    if len(data) < 6 or data[0] != 0x80:
        return False
    descriptor = data[2]
    chunk_index = descriptor >> 4
    total_chunks = descriptor & 0x0F
    if not (2 <= total_chunks <= 8 and chunk_index < total_chunks):
        return False
    pad_len = int.from_bytes(data[3:5], "big")
    return 5 + pad_len < len(data)


def looks_like_hysteria(data: bytes, config: EdgeClassifierConfig) -> bool:
    if not config.hysteria_enabled:
        return False
    mode = config.hysteria_mode.strip().lower()
    if mode in {"salamander", "gecko"}:
        plain = _salamander_plain(data, config.hysteria_password)
        return looks_like_quic_long_header(plain) or (mode == "gecko" and looks_like_gecko_frame(plain))
    return False


def classify_initial_datagram(data: bytes, config: EdgeClassifierConfig) -> Protocol | None:
    if looks_like_awg31(data, config):
        return "awg31"
    if looks_like_hysteria(data, config):
        return "hysteria2"
    hysteria_marked = config.hysteria_mode.strip().lower() in {"salamander", "gecko"}
    if config.tuic_enabled and looks_like_quic_long_header(data) and (not config.hysteria_enabled or hysteria_marked):
        return "tuic"
    if config.hysteria_enabled and not config.tuic_enabled and looks_like_quic_long_header(data):
        return "hysteria2"
    return None


def load_classifier_config() -> EdgeClassifierConfig:
    from app.connections.awg31 import get_settings as get_awg31_settings
    from app.connections.settings import get_connection_settings

    awg = get_awg31_settings()
    h1_low, h1_high = parse_range(awg.parameters.get("H1"))
    h4_low, h4_high = parse_range(awg.parameters.get("H4"))
    xray = get_connection_settings("xray")
    xcfg = dict(xray.config)
    mihomo = get_connection_settings("mihomo")
    mcfg = dict(mihomo.config)
    return EdgeClassifierConfig(
        awg_enabled=bool(awg.enabled),
        awg_header_key=decode_header_key(awg.header_protection_key),
        awg_s1=int(awg.parameters.get("S1") or 0), awg_h1_low=h1_low, awg_h1_high=h1_high,
        awg_s4=int(awg.parameters.get("S4") or 0), awg_h4_low=h4_low, awg_h4_high=h4_high,
        awg_random_trailers=str(awg.parameters.get("RandomTrailers") or "off").lower() == "on",
        hysteria_enabled=bool(xcfg.get("hysteria2_enabled")),
        hysteria_mode=str(xcfg.get("hysteria2_obfs_mode") or "none").strip().lower(),
        hysteria_password=str(xcfg.get("hysteria2_obfs_password") or "").encode("utf-8"),
        tuic_enabled=bool(mcfg.get("tuic_enabled")),
    )

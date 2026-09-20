from __future__ import annotations

import hashlib

from app.udp_edge.classifier import (
    EdgeClassifierConfig,
    _chacha20_prefix,
    classify_initial_datagram,
    looks_like_quic_long_header,
)


def _quic_initial() -> bytes:
    # Minimal structurally-valid long-header packet for classifier purposes.
    return bytes.fromhex("c00000000108") + b"12345678" + bytes([8]) + b"ABCDEFGH" + b"payload"


def _salamander_wrap(payload: bytes, password: bytes, salt: bytes = b"12345678") -> bytes:
    mask = hashlib.blake2b(password + salt, digest_size=32).digest()
    encoded = bytes(value ^ mask[index % 32] for index, value in enumerate(payload))
    return salt + encoded


def _awg_packet(key: bytes, *, padding: int, header: int, body_length: int) -> bytes:
    nonce = bytes(range(12))
    prefix = nonce + bytes(max(0, padding - len(nonce)))
    mask = _chacha20_prefix(key, nonce)
    encoded_header = bytes(
        value ^ mask[index]
        for index, value in enumerate(header.to_bytes(4, "little"))
    )
    body = bytearray(body_length)
    body[:4] = encoded_header
    return prefix + bytes(body)


def test_chacha20_prefix_matches_rfc8439_block_prefix():
    key = bytes(range(32))
    nonce = bytes.fromhex("000000090000004a00000000")
    # RFC 8439 §2.3.2 block with counter=1 differs from AWG counter=0, so
    # lock our counter=0 primitive with an independently precomputed prefix.
    assert _chacha20_prefix(key, nonce).hex() == "8adc91fd"


def test_awg31_initiation_wins_before_quic_classification():
    key = bytes(range(32))
    packet = _awg_packet(key, padding=64, header=1085466381, body_length=148)
    cfg = EdgeClassifierConfig(
        awg_enabled=True,
        awg_header_key=key,
        awg_s1=64,
        awg_h1_low=1085466381,
        awg_h1_high=1085466381,
        awg_s4=12,
        awg_h4_low=2767261704,
        awg_h4_high=2767261704,
        tuic_enabled=True,
    )
    assert classify_initial_datagram(packet, cfg) == "awg31"


def test_salamander_wrapped_quic_is_hysteria2():
    password = b"secret-password"
    packet = _salamander_wrap(_quic_initial(), password)
    cfg = EdgeClassifierConfig(
        hysteria_enabled=True,
        hysteria_mode="salamander",
        hysteria_password=password,
        tuic_enabled=True,
    )
    assert classify_initial_datagram(packet, cfg) == "hysteria2"


def test_plain_quic_is_tuic_when_hysteria_has_marker():
    packet = _quic_initial()
    assert looks_like_quic_long_header(packet)
    cfg = EdgeClassifierConfig(
        hysteria_enabled=True,
        hysteria_mode="salamander",
        hysteria_password=b"secret-password",
        tuic_enabled=True,
    )
    assert classify_initial_datagram(packet, cfg) == "tuic"


def test_plain_quic_is_dropped_when_hysteria_and_tuic_are_ambiguous():
    cfg = EdgeClassifierConfig(
        hysteria_enabled=True,
        hysteria_mode="none",
        tuic_enabled=True,
    )
    assert classify_initial_datagram(_quic_initial(), cfg) is None


def test_plain_quic_can_be_hysteria_when_tuic_is_disabled():
    cfg = EdgeClassifierConfig(hysteria_enabled=True, hysteria_mode="none", tuic_enabled=False)
    assert classify_initial_datagram(_quic_initial(), cfg) == "hysteria2"


def test_random_udp_is_never_guessed():
    cfg = EdgeClassifierConfig(
        awg_enabled=True,
        awg_header_key=bytes(range(32)),
        awg_s1=64,
        awg_h1_low=1085466381,
        awg_h1_high=1085466381,
        hysteria_enabled=True,
        hysteria_mode="salamander",
        hysteria_password=b"secret-password",
        tuic_enabled=True,
    )
    assert classify_initial_datagram(b"not-a-protocol-packet", cfg) is None

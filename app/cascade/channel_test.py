from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .adapters import xray_outbound
from .runtime import CascadeError


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _query(uri: str):
    parts = urlsplit(uri)
    return parts, parse_qs(parts.query, keep_blank_values=True)


def _one(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return str(values[0]) if values else default


def singbox_outbound(channel: dict) -> dict:
    channel_id = str(channel.get("id") or "")
    uri = str(channel.get("payload") or "").strip()
    parts, query = _query(uri)
    if not parts.hostname or not parts.port:
        raise CascadeError(f"{channel_id}: неверный endpoint")

    tls = {
        "enabled": True,
        "server_name": _one(query, "sni", parts.hostname),
        "insecure": False,
    }
    alpn = _one(query, "alpn")
    if alpn:
        tls["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]

    if channel_id == "anytls":
        if parts.scheme != "anytls":
            raise CascadeError("anytls: ожидается anytls://")
        password = unquote(parts.username or "")
        if not password:
            raise CascadeError("anytls: отсутствует password")
        return {
            "type": "anytls",
            "tag": "cascade-out",
            "server": parts.hostname,
            "server_port": int(parts.port),
            "password": password,
            "client_metadata": "",
            "tls": tls,
        }

    if channel_id == "tuic":
        if parts.scheme != "tuic":
            raise CascadeError("tuic: ожидается tuic://")
        user = unquote(parts.username or "")
        password = unquote(parts.password or "")
        if not user or not password:
            raise CascadeError("tuic: отсутствуют uuid/password")
        return {
            "type": "tuic",
            "tag": "cascade-out",
            "server": parts.hostname,
            "server_port": int(parts.port),
            "uuid": user,
            "password": password,
            "congestion_control": _one(query, "congestion_control", "bbr"),
            "udp_relay_mode": _one(query, "udp_relay_mode", "native"),
            "tls": tls,
        }

    if channel_id == "naiveproxy":
        if parts.scheme != "naive+https":
            raise CascadeError("naiveproxy: ожидается naive+https://")
        user = unquote(parts.username or "")
        password = unquote(parts.password or "")
        if not user or not password:
            raise CascadeError("naiveproxy: отсутствуют username/password")
        return {
            "type": "naive",
            "tag": "cascade-out",
            "server": parts.hostname,
            "server_port": int(parts.port),
            "username": user,
            "password": password,
            "insecure_concurrency": 0,
            "tls": tls,
        }

    raise CascadeError(f"{channel_id}: нет sing-box adapter")


def _curl_through_socks(port: int, family: str, timeout: int) -> dict:
    curl = shutil.which("curl")
    if not curl:
        return {"ok": False, "ip": "", "message": "curl не найден"}
    url = "https://api4.ipify.org" if family == "ipv4" else "https://api6.ipify.org"
    command = [
        curl,
        "-4" if family == "ipv4" else "-6",
        "--silent", "--show-error", "--fail",
        "--max-time", str(max(5, min(timeout, 20))),
        "--socks5-hostname", f"127.0.0.1:{port}",
        url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "ip": "", "message": "timeout"}
    ip = (result.stdout or "").strip()
    ok = result.returncode == 0 and bool(ip)
    return {
        "ok": ok,
        "ip": ip if ok else "",
        "message": "OK" if ok else (result.stderr or result.stdout or "Проверка не пройдена").strip(),
    }


def _wait_port(process: subprocess.Popen, port: int, seconds: float = 6.0) -> tuple[bool, str]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True, ""
        except OSError:
            time.sleep(0.1)
    error = ""
    if process.poll() is not None and process.stderr:
        try:
            error = process.stderr.read().strip()
        except Exception:
            error = ""
    return False, error


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def test_xray(channel: dict, timeout: int = 25) -> dict:
    xray = shutil.which("xray") or ("/usr/local/bin/xray" if Path("/usr/local/bin/xray").is_file() else "")
    if not xray:
        raise CascadeError("Xray не найден")
    port = _free_port()
    outbound = xray_outbound(channel)
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{"tag": "test-in", "listen": "127.0.0.1", "port": port, "protocol": "socks", "settings": {"auth": "noauth", "udp": False}}],
        "outbounds": [outbound],
        "routing": {"rules": [{"type": "field", "inboundTag": ["test-in"], "outboundTag": outbound["tag"]}]},
    }
    with tempfile.TemporaryDirectory(prefix="sg-cascade-xray-") as directory:
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        process = subprocess.Popen([str(xray), "run", "-config", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, detail = _wait_port(process, port)
            if not ready:
                raise CascadeError(detail or "Xray test SOCKS не поднялся")
            return {family: _curl_through_socks(port, family, timeout) for family in ("ipv4", "ipv6")}
        finally:
            _stop(process)


def test_singbox(channel: dict, timeout: int = 25) -> dict:
    binary = shutil.which("sing-box") or ("/usr/local/bin/sing-box" if Path("/usr/local/bin/sing-box").is_file() else "")
    if not binary:
        raise CascadeError("sing-box не найден")
    port = _free_port()
    outbound = singbox_outbound(channel)
    config = {
        "log": {"level": "warn"},
        "inbounds": [{"type": "socks", "tag": "test-in", "listen": "127.0.0.1", "listen_port": port}],
        "outbounds": [outbound],
        "route": {"final": "cascade-out"},
    }
    with tempfile.TemporaryDirectory(prefix="sg-cascade-singbox-") as directory:
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checked = subprocess.run([str(binary), "check", "-c", str(path)], capture_output=True, text=True, timeout=30, check=False)
        if checked.returncode != 0:
            raise CascadeError((checked.stderr or checked.stdout or "sing-box check failed").strip())
        process = subprocess.Popen([str(binary), "run", "-c", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, detail = _wait_port(process, port)
            if not ready:
                raise CascadeError(detail or "sing-box test SOCKS не поднялся")
            return {family: _curl_through_socks(port, family, timeout) for family in ("ipv4", "ipv6")}
        finally:
            _stop(process)


def test_mieru(channel: dict, timeout: int = 25) -> dict:
    binary = shutil.which("mihomo") or ("/usr/local/bin/mihomo" if Path("/usr/local/bin/mihomo").is_file() else "")
    if not binary:
        raise CascadeError("Mihomo не найден")
    uri = str(channel.get("payload") or "").strip()
    parts, query = _query(uri)
    if parts.scheme != "mierus" or not parts.hostname:
        raise CascadeError("mieru: ожидается mierus://")
    port = _free_port()
    username = unquote(parts.username or "")
    password = unquote(parts.password or "")
    remote_port = int(_one(query, "port", "443"))
    proxy_name = "Cascade Mieru"
    body = "\n".join([
        f"mixed-port: {port}",
        "allow-lan: false",
        "mode: rule",
        "log-level: warning",
        "proxies:",
        f"  - name: \"{proxy_name}\"",
        "    type: mieru",
        f"    server: \"{parts.hostname}\"",
        f"    port: {remote_port}",
        "    transport: TCP",
        f"    username: \"{username}\"",
        f"    password: \"{password}\"",
        f"    multiplexing: {_one(query, 'multiplexing', 'MULTIPLEXING_LOW')}",
        f"    handshake-mode: {_one(query, 'handshake-mode', 'HANDSHAKE_STANDARD')}",
        "rules:",
        f"  - MATCH,{proxy_name}",
        "",
    ])
    with tempfile.TemporaryDirectory(prefix="sg-cascade-mihomo-") as directory:
        path = Path(directory) / "config.yaml"
        path.write_text(body, encoding="utf-8")
        checked = subprocess.run([str(binary), "-t", "-f", str(path)], capture_output=True, text=True, timeout=30, check=False)
        if checked.returncode != 0:
            raise CascadeError((checked.stderr or checked.stdout or "Mihomo check failed").strip())
        process = subprocess.Popen([str(binary), "-f", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, detail = _wait_port(process, port)
            if not ready:
                raise CascadeError(detail or "Mihomo test port не поднялся")
            return {family: _curl_through_socks(port, family, timeout) for family in ("ipv4", "ipv6")}
        finally:
            _stop(process)


def test_channel(channel: dict, timeout: int = 25) -> dict:
    channel_id = str(channel.get("id") or "")
    if channel_id in {"reality_tcp", "xhttp_reality", "xhttp_tls", "hysteria2"}:
        return test_xray(channel, timeout)
    if channel_id in {"anytls", "tuic", "naiveproxy"}:
        return test_singbox(channel, timeout)
    if channel_id == "mieru":
        return test_mieru(channel, timeout)
    if channel_id == "awg31":
        return {
            "ipv4": {"ok": False, "ip": "", "message": "Требуется privileged AWG network-namespace test"},
            "ipv6": {"ok": False, "ip": "", "message": "Требуется privileged AWG network-namespace test"},
        }
    raise CascadeError(f"Неизвестный канал: {channel_id}")

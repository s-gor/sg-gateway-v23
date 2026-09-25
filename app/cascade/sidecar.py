from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from app.cascade.adapters import xray_outbound
from app.cascade.channel_test import singbox_outbound
from app.connections.awg31_uri import decode_awg31_uri


SOCKS_PORT = 10490
AWG_NS_ADDRESS = "169.254.231.2"
AWG_HOST_ADDRESS = "169.254.231.1"
AWG_SUBNET = "169.254.231.0/30"
AWG_ROOT = Path("/opt/sg-gateway/awg31/bin")
AWG = AWG_ROOT / "awg"
AWG_QUICK = AWG_ROOT / "awg-quick"
AWG_GO = AWG_ROOT / "amneziawg-go"


class SidecarError(RuntimeError):
    pass


def _state_path() -> Path:
    explicit = os.getenv("SG_GATEWAY_CASCADE_STATE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    from app.config import load_config
    return load_config().data_dir / "cascade.json"


def _state() -> dict:
    try:
        payload = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SidecarError(f"Не удалось прочитать Cascade state: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("enabled"):
        raise SidecarError("Каскад выключен")
    return payload


def _active_channel(state: dict) -> dict:
    channels = state.get("channels")
    if not isinstance(channels, dict):
        raise SidecarError("Cascade bundle отсутствует")
    active_id = str(state.get("active_channel") or "").strip()
    item = channels.get(active_id)
    if not active_id or not isinstance(item, dict) or not item.get("ready"):
        raise SidecarError("Активный Cascade channel не готов")
    return dict(item)


def _write(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    os.chmod(path, 0o600)


def _exec_xray(channel: dict) -> None:
    binary = shutil.which("xray") or "/usr/local/bin/xray"
    if not Path(binary).is_file():
        raise SidecarError("Xray не найден")
    outbound = xray_outbound(channel)
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "cascade-socks-in", "listen": "127.0.0.1", "port": SOCKS_PORT,
            "protocol": "socks", "settings": {"auth": "noauth", "udp": True},
        }],
        "outbounds": [outbound],
        "routing": {"rules": [{
            "type": "field", "inboundTag": ["cascade-socks-in"], "outboundTag": outbound["tag"],
        }]},
    }
    directory = Path("/run/sg-gateway/cascade")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "xray.json"
    _write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    os.execv(str(binary), [str(binary), "run", "-config", str(path)])


def _exec_singbox(channel: dict) -> None:
    binary = shutil.which("sing-box") or "/usr/local/bin/sing-box"
    if not Path(binary).is_file():
        raise SidecarError("sing-box не найден")
    outbound = singbox_outbound(channel)
    config = {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "socks", "tag": "cascade-socks-in",
            "listen": "127.0.0.1", "listen_port": SOCKS_PORT,
        }],
        "outbounds": [outbound],
        "route": {"final": "cascade-out"},
    }
    directory = Path("/run/sg-gateway/cascade")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sing-box.json"
    _write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    checked = subprocess.run([str(binary), "check", "-c", str(path)], capture_output=True, text=True, timeout=30, check=False)
    if checked.returncode != 0:
        raise SidecarError((checked.stderr or checked.stdout or "sing-box check failed").strip())
    os.execv(str(binary), [str(binary), "run", "-c", str(path)])


def _exec_mieru(channel: dict) -> None:
    binary = shutil.which("mihomo") or "/usr/local/bin/mihomo"
    if not Path(binary).is_file():
        raise SidecarError("Mihomo не найден")
    uri = str(channel.get("payload") or "").strip()
    parts = urlsplit(uri)
    query = parse_qs(parts.query, keep_blank_values=True)
    if parts.scheme != "mierus" or not parts.hostname:
        raise SidecarError("Mieru Cascade URI повреждён")
    def q(name: str, default: str) -> str:
        values = query.get(name)
        return str(values[0]) if values else default
    username = unquote(parts.username or "")
    password = unquote(parts.password or "")
    port = int(q("port", "443"))
    body = "\n".join([
        f"mixed-port: {SOCKS_PORT}",
        "bind-address: 127.0.0.1",
        "allow-lan: false",
        "mode: rule",
        "log-level: warning",
        "proxies:",
        '  - name: "Cascade Mieru"',
        "    type: mieru",
        f'    server: "{parts.hostname}"',
        f"    port: {port}",
        "    transport: TCP",
        f'    username: "{username}"',
        f'    password: "{password}"',
        f"    multiplexing: {q('multiplexing', 'MULTIPLEXING_LOW')}",
        f"    handshake-mode: {q('handshake-mode', 'HANDSHAKE_STANDARD')}",
        "rules:",
        "  - MATCH,Cascade Mieru",
        "",
    ])
    directory = Path("/run/sg-gateway/cascade")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "mihomo.yaml"
    _write(path, body)
    checked = subprocess.run([str(binary), "-t", "-f", str(path)], capture_output=True, text=True, timeout=30, check=False)
    if checked.returncode != 0:
        raise SidecarError((checked.stderr or checked.stdout or "Mihomo check failed").strip())
    os.execv(str(binary), [str(binary), "-f", str(path)])


def _run(command: list[str], *, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise SidecarError((result.stderr or result.stdout or "command failed").strip())
    return result


def _resolve4(host: str) -> str:
    rows = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_DGRAM)
    if not rows:
        raise SidecarError("Не удалось разрешить AWG endpoint")
    return str(rows[0][4][0])


def _awg_endpoint(endpoint: str) -> tuple[str, int]:
    parsed = urlsplit("//" + endpoint)
    if not parsed.hostname or not parsed.port:
        raise SidecarError("AWG endpoint повреждён")
    return parsed.hostname, int(parsed.port)


def _rewrite_awg_config(config: str, endpoint_ip: str, port: int) -> tuple[str, str]:
    address_match = re.search(r"(?mi)^Address\s*=\s*([^,\s]+)", config)
    if not address_match:
        raise SidecarError("AWG config не содержит Address")
    address = address_match.group(1).strip()
    body, count = re.subn(
        r"(?mi)^Endpoint\s*=\s*.*$",
        f"Endpoint = {endpoint_ip}:{port}",
        config,
        count=1,
    )
    if count != 1:
        raise SidecarError("AWG config не содержит Endpoint")
    return body.rstrip() + "\n", address


def _cleanup_awg(ns: str, host_veth: str, nft_table: str, children: list[subprocess.Popen]) -> None:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
    _run(["nft", "delete", "table", "ip", nft_table], check=False)
    _run(["ip", "link", "delete", host_veth], check=False)
    _run(["ip", "netns", "delete", ns], check=False)


def _run_awg(channel: dict) -> None:
    for path in (AWG, AWG_QUICK, AWG_GO):
        if not path.is_file():
            raise SidecarError(f"AWG runtime отсутствует: {path}")
    singbox = shutil.which("sing-box") or "/usr/local/bin/sing-box"
    if not Path(singbox).is_file():
        raise SidecarError("sing-box не найден для AWG SOCKS bridge")

    decoded = decode_awg31_uri(str(channel.get("payload") or ""))
    endpoint_host, endpoint_port = _awg_endpoint(str(decoded["endpoint"]))
    endpoint_ip = _resolve4(endpoint_host)
    config, address = _rewrite_awg_config(str(decoded["config"]), endpoint_ip, endpoint_port)

    ns = "sg-cascade-awg"
    host_veth = "sgcawgh"
    ns_veth = "sgcawgn"
    iface = "sgcawg0"
    nft_table = "sg_cascade_awg"
    children: list[subprocess.Popen] = []
    old_forward = Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()

    def cleanup(*_args) -> None:
        _cleanup_awg(ns, host_veth, nft_table, children)
        if old_forward != "1":
            _run(["sysctl", "-w", f"net.ipv4.ip_forward={old_forward}"], check=False)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    _cleanup_awg(ns, host_veth, nft_table, [])
    try:
        _run(["ip", "netns", "add", ns])
        _run(["ip", "link", "add", host_veth, "type", "veth", "peer", "name", ns_veth])
        _run(["ip", "link", "set", ns_veth, "netns", ns])
        _run(["ip", "address", "add", f"{AWG_HOST_ADDRESS}/30", "dev", host_veth])
        _run(["ip", "link", "set", host_veth, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"])
        _run(["ip", "netns", "exec", ns, "ip", "address", "add", f"{AWG_NS_ADDRESS}/30", "dev", ns_veth])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", ns_veth, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "route", "add", "default", "via", AWG_HOST_ADDRESS, "dev", ns_veth])
        if old_forward != "1":
            _run(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        default = _run(["ip", "-4", "route", "show", "default"]).stdout.splitlines()[0].split()
        wan_if = default[default.index("dev") + 1]
        _run(["nft", "add", "table", "ip", nft_table])
        _run(["nft", "add", "chain", "ip", nft_table, "forward", "{", "type", "filter", "hook", "forward", "priority", "filter", ";", "policy", "accept", ";", "}"])
        _run(["nft", "add", "chain", "ip", nft_table, "postrouting", "{", "type", "nat", "hook", "postrouting", "priority", "srcnat", ";", "policy", "accept", ";", "}"])
        _run(["nft", "add", "rule", "ip", nft_table, "postrouting", "oifname", wan_if, "ip", "saddr", AWG_SUBNET, "masquerade"])

        awg_go = subprocess.Popen(
            ["ip", "netns", "exec", ns, "env", "WG_PROCESS_FOREGROUND=1", str(AWG_GO), "--foreground", iface],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        children.append(awg_go)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if awg_go.poll() is not None:
                raise SidecarError((awg_go.stderr.read() if awg_go.stderr else "") or "AWG daemon stopped")
            if _run(["ip", "netns", "exec", ns, "ip", "link", "show", iface], check=False).returncode == 0:
                break
            time.sleep(.1)
        else:
            raise SidecarError("AWG Cascade interface не появился")

        with tempfile.TemporaryDirectory(prefix="sg-cascade-awg-runtime-") as directory:
            cfg = Path(directory) / "awg.conf"
            stripped = Path(directory) / "stripped.conf"
            _write(cfg, config)
            _write(stripped, _run([str(AWG_QUICK), "strip", str(cfg)]).stdout)
            _run(["ip", "netns", "exec", ns, str(AWG), "setconf", iface, str(stripped)])

        _run(["ip", "netns", "exec", ns, "ip", "address", "add", address, "dev", iface])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", "mtu", "1280", "up", "dev", iface])
        _run(["ip", "netns", "exec", ns, "ip", "route", "replace", f"{endpoint_ip}/32", "via", AWG_HOST_ADDRESS, "dev", ns_veth])
        _run(["ip", "netns", "exec", ns, "ip", "route", "replace", "default", "dev", iface])

        directory = Path("/run/sg-gateway/cascade")
        directory.mkdir(parents=True, exist_ok=True)
        sb = directory / "awg-bridge.json"
        _write(sb, json.dumps({
            "log": {"level": "warn"},
            "inbounds": [{"type": "socks", "tag": "cascade-socks-in", "listen": AWG_NS_ADDRESS, "listen_port": SOCKS_PORT}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
            "route": {"final": "direct"},
        }, ensure_ascii=False, indent=2) + "\n")
        bridge = subprocess.Popen(
            ["ip", "netns", "exec", ns, str(singbox), "run", "-c", str(sb)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        children.append(bridge)
        returncode = bridge.wait()
        if returncode != 0:
            raise SidecarError((bridge.stderr.read() if bridge.stderr else "") or "AWG SOCKS bridge stopped")
    finally:
        _cleanup_awg(ns, host_veth, nft_table, children)
        if old_forward != "1":
            _run(["sysctl", "-w", f"net.ipv4.ip_forward={old_forward}"], check=False)


def main() -> int:
    try:
        state = _state()
        channel = _active_channel(state)
        channel_id = str(channel.get("id") or "")
        if channel_id in {"reality_tcp", "xhttp_reality", "xhttp_tls", "hysteria2"}:
            _exec_xray(channel)
        elif channel_id in {"anytls", "tuic", "naiveproxy"}:
            _exec_singbox(channel)
        elif channel_id == "mieru":
            _exec_mieru(channel)
        elif channel_id == "awg31":
            _run_awg(channel)
        else:
            raise SidecarError(f"Неизвестный Cascade channel: {channel_id}")
    except Exception as exc:
        print(f"SG Cascade sidecar: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

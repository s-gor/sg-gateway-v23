from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.connections.awg31_uri import decode_awg31_uri


AWG_ROOT = Path("/opt/sg-gateway/awg31/bin")
AWG = AWG_ROOT / "awg"
AWG_QUICK = AWG_ROOT / "awg-quick"
AWG_GO = AWG_ROOT / "amneziawg-go"


def _run(command: list[str], *, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())
    return result


def _state_path() -> Path:
    explicit = os.getenv("SG_GATEWAY_CASCADE_STATE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data = Path(os.getenv("SG_GATEWAY_DATA_DIR", "/var/lib/sg-gateway"))
    return data / "cascade.json"


def _awg_uri() -> str:
    payload = json.loads(_state_path().read_text(encoding="utf-8"))
    channels = payload.get("channels") if isinstance(payload, dict) else None
    item = channels.get("awg31") if isinstance(channels, dict) else None
    uri = str(item.get("payload") or "").strip() if isinstance(item, dict) else ""
    if not uri:
        raise RuntimeError("AWG3.1 Cascade access отсутствует")
    return uri


def _endpoint_parts(endpoint: str) -> tuple[str, int]:
    parsed = urlsplit("//" + endpoint)
    if not parsed.hostname or not parsed.port:
        raise RuntimeError("AWG3.1 endpoint повреждён")
    return parsed.hostname, int(parsed.port)


def _resolve_ipv4(host: str) -> str:
    for family, _, _, _, sockaddr in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_DGRAM):
        if family == socket.AF_INET and sockaddr:
            return str(sockaddr[0])
    raise RuntimeError("Не удалось получить IPv4 адрес AWG3.1 endpoint")


def _rewrite_endpoint(config: str, endpoint_ip: str, port: int) -> str:
    replacement = f"Endpoint = {endpoint_ip}:{port}"
    lines = []
    replaced = False
    for raw in config.splitlines():
        if raw.strip().lower().startswith("endpoint ="):
            lines.append(replacement)
            replaced = True
        else:
            lines.append(raw)
    if not replaced:
        raise RuntimeError("AWG3.1 config не содержит Endpoint")
    return "\n".join(lines).rstrip() + "\n"


def _interface_address(config: str) -> str:
    match = re.search(r"(?mi)^Address\s*=\s*([^,\s]+)", config)
    if not match:
        raise RuntimeError("AWG3.1 config не содержит Address")
    return match.group(1).strip()


def _cleanup(ns: str, host_veth: str, table: str, process: subprocess.Popen | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    _run(["nft", "delete", "table", "ip", table], check=False)
    _run(["ip", "link", "delete", host_veth], check=False)
    _run(["ip", "netns", "delete", ns], check=False)


def run_test() -> dict:
    for path in (AWG, AWG_QUICK, AWG_GO):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"AWG3.1 runtime отсутствует: {path}")
    for command in ("ip", "nft", "curl"):
        if not shutil.which(command):
            raise RuntimeError(f"Для AWG3.1 test не найдена команда {command}")

    decoded = decode_awg31_uri(_awg_uri())
    endpoint_host, endpoint_port = _endpoint_parts(str(decoded["endpoint"]))
    endpoint_ip = _resolve_ipv4(endpoint_host)
    config = _rewrite_endpoint(str(decoded["config"]), endpoint_ip, endpoint_port)
    address = _interface_address(config)

    suffix = str(os.getpid())[-5:]
    ns = f"sgcawg{suffix}"
    host_veth = f"sgch{suffix}"
    ns_veth = f"sgcn{suffix}"
    iface = "sgctest0"
    table = f"sgcawg{suffix}"
    host_cidr = "169.254.230.1/30"
    ns_cidr = "169.254.230.2/30"
    gateway = "169.254.230.1"
    process = None
    old_forward = Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()
    try:
        _cleanup(ns, host_veth, table, None)
        _run(["ip", "netns", "add", ns])
        _run(["ip", "link", "add", host_veth, "type", "veth", "peer", "name", ns_veth])
        _run(["ip", "link", "set", ns_veth, "netns", ns])
        _run(["ip", "address", "add", host_cidr, "dev", host_veth])
        _run(["ip", "link", "set", host_veth, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"])
        _run(["ip", "netns", "exec", ns, "ip", "address", "add", ns_cidr, "dev", ns_veth])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", ns_veth, "up"])
        _run(["ip", "netns", "exec", ns, "ip", "route", "add", "default", "via", gateway, "dev", ns_veth])

        if old_forward != "1":
            _run(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        wan = _run(["ip", "-4", "route", "show", "default"]).stdout.splitlines()
        if not wan:
            raise RuntimeError("Default WAN route не найден")
        words = wan[0].split()
        wan_if = words[words.index("dev") + 1] if "dev" in words else ""
        if not wan_if:
            raise RuntimeError("Default WAN interface не найден")

        _run(["nft", "add", "table", "ip", table])
        _run(["nft", "add", "chain", "ip", table, "forward", "{", "type", "filter", "hook", "forward", "priority", "filter", ";", "policy", "accept", ";", "}"])
        _run(["nft", "add", "chain", "ip", table, "postrouting", "{", "type", "nat", "hook", "postrouting", "priority", "srcnat", ";", "policy", "accept", ";", "}"])
        _run(["nft", "add", "rule", "ip", table, "postrouting", "oifname", wan_if, "ip", "saddr", "169.254.230.0/30", "masquerade"])

        process = subprocess.Popen(
            ["ip", "netns", "exec", ns, "env", "WG_PROCESS_FOREGROUND=1", str(AWG_GO), "--foreground", iface],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if process.poll() is not None:
                detail = process.stderr.read().strip() if process.stderr else ""
                raise RuntimeError(detail or "amneziawg-go завершился раньше времени")
            if _run(["ip", "netns", "exec", ns, "ip", "link", "show", iface], check=False).returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError("AWG3.1 test interface не появился")

        with tempfile.TemporaryDirectory(prefix="sg-cascade-awg-") as directory:
            cfg = Path(directory) / "awg.conf"
            stripped = Path(directory) / "stripped.conf"
            cfg.write_text(config, encoding="utf-8")
            stripped.write_text(_run([str(AWG_QUICK), "strip", str(cfg)]).stdout, encoding="utf-8")
            _run(["ip", "netns", "exec", ns, str(AWG), "setconf", iface, str(stripped)])

        _run(["ip", "netns", "exec", ns, "ip", "address", "add", address, "dev", iface])
        _run(["ip", "netns", "exec", ns, "ip", "link", "set", "mtu", "1280", "up", "dev", iface])
        _run(["ip", "netns", "exec", ns, "ip", "route", "replace", f"{endpoint_ip}/32", "via", gateway, "dev", ns_veth])
        _run(["ip", "netns", "exec", ns, "ip", "route", "replace", "default", "dev", iface])

        api_ip = _resolve_ipv4("api4.ipify.org")
        result = _run(
            [
                "ip", "netns", "exec", ns, "curl",
                "--silent", "--show-error", "--fail", "--max-time", "20",
                "--resolve", f"api4.ipify.org:443:{api_ip}",
                "https://api4.ipify.org",
            ],
            timeout=25,
            check=False,
        )
        ip = (result.stdout or "").strip()
        if result.returncode != 0 or not ip:
            raise RuntimeError((result.stderr or result.stdout or "AWG3.1 traffic test failed").strip())
        return {
            "ok": True,
            "message": "AWG3.1 проверен в изолированном network namespace",
            "ipv4": {"ok": True, "ip": ip, "message": "OK"},
            "ipv6": {"ok": False, "ip": "", "message": "IPv6 AWG namespace test не выполнялся"},
        }
    finally:
        _cleanup(ns, host_veth, table, process)
        if old_forward != "1":
            _run(["sysctl", "-w", f"net.ipv4.ip_forward={old_forward}"], check=False)


def main(argv: list[str] | None = None) -> int:
    action = (argv or sys.argv[1:] or ["test"])[0]
    if action != "test":
        print(json.dumps({"ok": False, "message": "Unsupported action"}))
        return 2
    try:
        payload = run_test()
    except Exception as exc:
        print(json.dumps({"ok": False, "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

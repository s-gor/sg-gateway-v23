from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlsplit

from .runtime import CASCADE_CORE_TAG, CascadeError


def _one(query: dict[str, list[str]], *names: str, default: str = "") -> str:
    for name in names:
        values = query.get(name)
        if values:
            return str(values[0])
    return default


def _vless_outbound(uri: str, channel_id: str) -> dict:
    parts = urlsplit(uri)
    if parts.scheme.lower() != "vless" or not parts.hostname or not parts.port:
        raise CascadeError(f"{channel_id}: ожидается VLESS URI")
    user_id = unquote(parts.username or "").strip()
    if not user_id:
        raise CascadeError(f"{channel_id}: отсутствует UUID")
    query = parse_qs(parts.query, keep_blank_values=True)
    network = _one(query, "type", default="tcp").strip().lower() or "tcp"
    security = _one(query, "security", default="none").strip().lower() or "none"
    user: dict = {
        "id": user_id,
        "encryption": _one(query, "encryption", default="none") or "none",
    }
    flow = _one(query, "flow")
    if flow:
        user["flow"] = flow

    stream: dict = {"network": network, "security": security}
    if network == "xhttp":
        xhttp: dict = {}
        path = _one(query, "path")
        mode = _one(query, "mode")
        host = _one(query, "host")
        extra = _one(query, "extra")
        if path:
            xhttp["path"] = path
        if mode:
            xhttp["mode"] = mode
        if host:
            xhttp["host"] = host
        if extra:
            try:
                parsed = json.loads(extra)
                if isinstance(parsed, dict):
                    xhttp.update(parsed)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        stream["xhttpSettings"] = xhttp

    if security == "reality":
        reality = {
            "serverName": _one(query, "sni", "serverName"),
            "fingerprint": _one(query, "fp", default="chrome") or "chrome",
            "publicKey": _one(query, "pbk", "publicKey"),
            "shortId": _one(query, "sid", "shortId"),
        }
        spider = _one(query, "spx", "spiderX")
        if spider:
            reality["spiderX"] = spider
        stream["realitySettings"] = reality
    elif security == "tls":
        tls = {
            "serverName": _one(query, "sni", "serverName"),
            "fingerprint": _one(query, "fp", default="chrome") or "chrome",
        }
        alpn = _one(query, "alpn")
        if alpn:
            tls["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]
        stream["tlsSettings"] = tls

    return {
        "tag": CASCADE_CORE_TAG,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": parts.hostname,
                    "port": int(parts.port),
                    "users": [user],
                }
            ]
        },
        "streamSettings": stream,
    }


def _hysteria2_outbound(uri: str) -> dict:
    parts = urlsplit(uri)
    if parts.scheme.lower() not in {"hysteria2", "hy2"} or not parts.hostname or not parts.port:
        raise CascadeError("hysteria2: ожидается Hysteria2 URI")
    auth = unquote(parts.username or "").strip()
    if not auth:
        raise CascadeError("hysteria2: отсутствует auth")
    query = parse_qs(parts.query, keep_blank_values=True)
    tls = {
        "serverName": _one(query, "sni"),
        "alpn": ["h3"],
        "allowInsecure": _one(query, "insecure", default="0") in {"1", "true", "yes"},
    }
    hysteria: dict = {"version": 2, "auth": auth}
    obfs = _one(query, "obfs")
    obfs_password = _one(query, "obfs-password")
    if obfs and obfs_password:
        hysteria["udpmasks"] = [
            {"type": obfs, "settings": {"password": obfs_password}}
        ]
    return {
        "tag": CASCADE_CORE_TAG,
        "protocol": "hysteria",
        "settings": {
            "address": parts.hostname,
            "port": int(parts.port),
            "version": 2,
        },
        "streamSettings": {
            "network": "hysteria",
            "security": "tls",
            "tlsSettings": tls,
            "hysteriaSettings": hysteria,
        },
    }


def xray_outbound(channel: dict) -> dict:
    channel_id = str(channel.get("id") or "").strip()
    payload = str(channel.get("payload") or "").strip()
    if channel_id in {"reality_tcp", "xhttp_reality", "xhttp_tls"}:
        return _vless_outbound(payload, channel_id)
    if channel_id == "hysteria2":
        return _hysteria2_outbound(payload)
    raise CascadeError(f"{channel_id}: канал обслуживается не Xray-adapter")

from __future__ import annotations

import json
import os
import selectors
import signal
import socket
import time
from dataclasses import dataclass
from pathlib import Path

from app.single_edge import AWG31_UDP_INTERNAL_PORT, HYSTERIA2_UDP_INTERNAL_PORT, PUBLIC_UDP_PORT, TUIC_UDP_INTERNAL_PORT
from app.udp_edge.classifier import Protocol, classify_initial_datagram, load_classifier_config

BACKENDS: dict[Protocol, tuple[str, int]] = {
    "awg31": ("127.0.0.1", AWG31_UDP_INTERNAL_PORT),
    "hysteria2": ("127.0.0.1", HYSTERIA2_UDP_INTERNAL_PORT),
    "tuic": ("127.0.0.1", TUIC_UDP_INTERNAL_PORT),
}
SESSION_TTL = 300.0
MAX_SESSIONS = 4096
STATUS_PATH = Path("/run/sg-gateway/udp-edge-status.json")


@dataclass
class Session:
    protocol: Protocol
    client: tuple
    public_socket: socket.socket
    backend_socket: socket.socket
    last_seen: float


class UdpEdgeServer:
    def __init__(self) -> None:
        self.selector = selectors.DefaultSelector()
        self.sessions: dict[tuple, Session] = {}
        self.running = True
        self.config = load_classifier_config()
        self.config_loaded_at = time.monotonic()
        self.last_status = 0.0
        self.counters = {"awg31": 0, "hysteria2": 0, "tuic": 0, "unknown": 0, "sessions": 0}
        self.public_sockets: list[socket.socket] = []

    def _bind_public(self) -> None:
        for family, address in ((socket.AF_INET, ("0.0.0.0", PUBLIC_UDP_PORT)), (socket.AF_INET6, ("::", PUBLIC_UDP_PORT))):
            sock = socket.socket(family, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.setblocking(False)
            sock.bind(address)
            self.public_sockets.append(sock)
            self.selector.register(sock, selectors.EVENT_READ, ("public", sock))

    def _session_key(self, public_socket: socket.socket, client: tuple) -> tuple:
        return (public_socket.family, str(client[0]), int(client[1]))

    def _close_session(self, key: tuple) -> None:
        session = self.sessions.pop(key, None)
        if session is None:
            return
        try:
            self.selector.unregister(session.backend_socket)
        except Exception:
            pass
        session.backend_socket.close()

    def _new_session(self, key: tuple, protocol: Protocol, public_socket: socket.socket, client: tuple) -> Session:
        if len(self.sessions) >= MAX_SESSIONS:
            oldest = min(self.sessions, key=lambda item: self.sessions[item].last_seen)
            self._close_session(oldest)
        backend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        backend.setblocking(False)
        backend.connect(BACKENDS[protocol])
        session = Session(protocol, client, public_socket, backend, time.monotonic())
        self.sessions[key] = session
        self.selector.register(backend, selectors.EVENT_READ, ("backend", key))
        self.counters["sessions"] += 1
        return session

    def _reload_config_if_needed(self) -> None:
        now = time.monotonic()
        if now - self.config_loaded_at < 5.0:
            return
        self.config = load_classifier_config()
        self.config_loaded_at = now

    def _handle_public(self, sock: socket.socket) -> None:
        try:
            data, client = sock.recvfrom(65535)
        except BlockingIOError:
            return
        self._reload_config_if_needed()
        key = self._session_key(sock, client)
        session = self.sessions.get(key)
        if session is None:
            protocol = classify_initial_datagram(data, self.config)
            if protocol is None:
                self.counters["unknown"] += 1
                return
            session = self._new_session(key, protocol, sock, client)
        session.last_seen = time.monotonic()
        self.counters[session.protocol] += 1
        try:
            session.backend_socket.send(data)
        except OSError:
            self._close_session(key)

    def _handle_backend(self, key: tuple) -> None:
        session = self.sessions.get(key)
        if session is None:
            return
        try:
            data = session.backend_socket.recv(65535)
        except BlockingIOError:
            return
        except OSError:
            self._close_session(key)
            return
        session.last_seen = time.monotonic()
        try:
            session.public_socket.sendto(data, session.client)
        except OSError:
            self._close_session(key)

    def _expire(self) -> None:
        deadline = time.monotonic() - SESSION_TTL
        for key, session in list(self.sessions.items()):
            if session.last_seen < deadline:
                self._close_session(key)

    def _write_status(self) -> None:
        now = time.monotonic()
        if now - self.last_status < 5.0:
            return
        self.last_status = now
        payload = {"public_udp_port": PUBLIC_UDP_PORT, "active_sessions": len(self.sessions), "counters": dict(self.counters), "updated_at": int(time.time())}
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATUS_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, STATUS_PATH)

    def stop(self, *_args) -> None:
        self.running = False

    def run(self) -> None:
        self._bind_public()
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        while self.running:
            for key, _mask in self.selector.select(timeout=1.0):
                kind, value = key.data
                if kind == "public":
                    self._handle_public(value)
                else:
                    self._handle_backend(value)
            self._expire()
            self._write_status()
        for key in list(self.sessions):
            self._close_session(key)
        for sock in self.public_sockets:
            try:
                self.selector.unregister(sock)
            except Exception:
                pass
            sock.close()


def main() -> None:
    UdpEdgeServer().run()


if __name__ == "__main__":
    main()

# SG-Gateway 23.01 All-Protocol Single Edge 443 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every current SG-Gateway client protocol use public port 443 while keeping all protocol backends private and preserving panel TCP 63443.

**Architecture:** Nginx remains the single TCP/443 owner and dispatches TLS/Reality traffic plus a deterministic non-TLS Mieru/TCP fallback. A new SG-Gateway UDP edge service becomes the single UDP/443 owner and session-aware dispatcher for AWG31, Hysteria2, TUIC and optional Mieru/UDP. QUIC protocol separation must use deterministic first-flight classification; no SO_REUSEPORT lottery is permitted.

**Tech Stack:** Python 3, Nginx stream ssl_preread, systemd, Xray, Mihomo, sing-box, AmneziaWG 3.1, Caddy/NaiveProxy, pytest, Ubuntu 24.04.

**Spec:** `docs/superpowers/specs/2026-09-16-single-edge-443-all-protocols-design.md`

## Global Constraints

- Public protocol ingress is exactly `443/tcp` and `443/udp`.
- Panel stays on `63443/tcp` (or configured panel port); ACME/HTTP stays on `80/tcp`.
- All backend listeners are private implementation details and never appear in client exports.
- PR #5 remains draft and is not merged before complete live acceptance.
- Existing credentials and keys must survive update and rollback.
- Unknown UDP traffic is dropped, never guessed into a backend.
- No live-server sed/FIX scripts; the repository remains the source of truth.

---

### Task 1: Lock the public-port contract with failing tests

**Files:**
- Modify: `tests/test_2301_single_edge_tls_hub.py`
- Create: `tests/test_2301_single_edge_all_protocol_exports.py`
- Create: `tests/test_2301_single_edge_udp_contract.py`

**Interfaces:**
- Consumes: existing export builders and `app.single_edge` constants.
- Produces: regression contract requiring public port 443 for every current protocol and exactly one UDP edge owner.

- [ ] Add tests that build AWG31, Reality, XHTTP/Reality, XHTTP/TLS, Hysteria2, Mieru, AnyTLS, TUIC and NaiveProxy exports and assert every public endpoint is `:443`.
- [ ] Add tests that reject public internal ports `2099`, `8443`, `8446`, `9443`, `10443`, `10444`, `10445`, `10447` in exported links/YAML/configs.
- [ ] Add installer/runtime-text tests asserting protocol backends do not bind public UDP/443 and a dedicated UDP edge unit is the only UDP/443 owner.
- [ ] Run the focused tests and verify they fail on current `ced7...` behavior before implementation.

### Task 2: Centralize internal backend addresses

**Files:**
- Modify: `app/single_edge.py`
- Modify: `hostd/sg_hostd/client_runtime.py`
- Modify: `app/mihomo/service.py`
- Test: `tests/test_2301_single_edge_udp_contract.py`

**Interfaces:**
- Produces constants for every private backend and public `443` values used by runtime generators and exports.

- [ ] Define non-conflicting private backend ports for AWG31 UDP, Hysteria2 UDP, TUIC UDP and Mieru UDP/TCP/AnyTLS TCP.
- [ ] Change runtime generation so protocol services bind only loopback/private addresses and those backend ports.
- [ ] Preserve Xray Reality `10443/tcp`, XHTTP Reality `10444/tcp`, XHTTP TLS `10445/tcp`, Caddy `10447/tcp` unless a verified collision requires a change.
- [ ] Run focused runtime tests until all private-bind assertions pass.

### Task 3: Extend the TCP/443 edge to Mieru/TCP and AnyTLS

**Files:**
- Modify: `deploy/configure-panel-access.sh`
- Modify: `install.sh`
- Modify: `app/mihomo/service.py`
- Modify: `hostd/sg_hostd/client_runtime.py`
- Test: `tests/test_2301_single_edge_tls_hub.py`

**Interfaces:**
- Nginx consumes TLS SNI/ALPN and ssl_preread protocol metadata.
- Caddy continues to own the configured SG HTTPS SNI for NaiveProxy/XHTTP-TLS/placeholder.

- [ ] Add a deterministic TCP dispatch matrix: Reality SNI -> 10443; XHTTP Reality SNI -> 10444; SG HTTPS SNI -> Caddy; AnyTLS -> private AnyTLS backend via a dedicated exported TLS ALPN; non-TLS stream -> private Mieru/TCP backend when enabled; TLS with no recognized route -> placeholder.
- [ ] Make the AnyTLS ALPN an SG-Gateway system contract rather than a user-editable accidental value and emit it in server/client configuration.
- [ ] Ensure disabling Mieru or AnyTLS makes the corresponding edge route disappear without breaking browser HTTPS.
- [ ] Validate Nginx configuration and run focused TCP edge tests.

### Task 4: Implement session-aware UDP edge service

**Files:**
- Create: `app/udp_edge/__init__.py`
- Create: `app/udp_edge/classifier.py`
- Create: `app/udp_edge/server.py`
- Create: `app/udp_edge/status.py`
- Create: `deploy/sg-gateway-udp-edge.service`
- Modify: `install.sh`
- Modify: `release-manifest.json`
- Test: `tests/test_2301_single_edge_udp_classifier.py`
- Test: `tests/test_2301_single_edge_udp_contract.py`

**Interfaces:**
- `classify_initial_datagram(data: bytes, config: EdgeClassifierConfig) -> Protocol | None`.
- `UdpEdgeServer` binds public `0.0.0.0:443` and `[::]:443`, maintains 5-tuple -> backend sessions, and relays replies with public source port 443.

- [ ] Implement AWG31 classification using the configured AWG31 packet-padding/header-protection parameters; validate the decoded message type/range rather than matching packet length alone.
- [ ] Implement Hysteria2 classification for Salamander/Gecko first flights using the configured obfuscation secret and QUIC structural validation.
- [ ] For unobfuscated QUIC, parse enough QUIC Initial/TLS ClientHello metadata to distinguish the fixed SG TUIC ALPN from Hysteria2 `h3`; reject ambiguous Initials.
- [ ] Treat Mieru/UDP as an explicit final classifier only when enabled and after AWG/QUIC validation has failed; add protocol-specific validation from the shipped Mieru format/credential metadata so random traffic is not blindly forwarded.
- [ ] Add per-session expiry, maximum table size, malformed-packet counters and per-protocol counters.
- [ ] Unit-test positive fixtures, collisions, malformed traffic, expiry and reply routing.

### Task 5: Move all UDP protocol runtimes behind the dispatcher

**Files:**
- Modify: `app/connections/awg31.py`
- Modify: `hostd/sg_hostd/client_runtime.py`
- Modify: `app/mihomo/service.py`
- Modify: `install.sh`
- Test: `tests/test_2301_single_edge_udp_contract.py`

**Interfaces:**
- Consumes private backend constants from `app.single_edge`.
- Produces runtime configurations that never bind public UDP/443 directly.

- [ ] Move AWG31 from public UDP/443 to private AWG31 backend.
- [ ] Move Hysteria2 from UDP/8446 to private Hysteria2 backend.
- [ ] Move TUIC from its existing public UDP port to private TUIC backend and use fixed SG TUIC ALPN for edge classification.
- [ ] If Mieru UDP is selected, move it to its private Mieru UDP backend.
- [ ] Verify only `sg-gateway-udp-edge.service` owns public UDP/443 when all protocols are enabled.

### Task 6: Rewrite every public export to 443

**Files:**
- Modify: `app/clients/exports.py`
- Modify: `app/mihomo/service.py`
- Modify: any protocol-specific URI builders reached by exports
- Test: `tests/test_2301_single_edge_all_protocol_exports.py`

**Interfaces:**
- Consumes `PUBLIC_TCP_PORT=443` / public UDP 443 contract.
- Produces direct links, QR source strings, subscriptions and YAML with public port 443 only.

- [ ] Force AWG31 endpoint to public 443 independent of private runtime port.
- [ ] Force Hysteria2 public port 443.
- [ ] Force Mieru public port 443 for both TCP and UDP transport selection.
- [ ] Force AnyTLS public port 443 and include its SG ALPN.
- [ ] Force TUIC public port 443 and include the fixed TUIC ALPN.
- [ ] Keep Reality/XHTTP/NaiveProxy at 443 and prevent regressions.
- [ ] Run all export/subscription/QR tests.

### Task 7: Make install/update/rollback transactional

**Files:**
- Modify: `install.sh`
- Modify: `deploy/update-from-github.sh`
- Modify: `deploy/update-from-github-core.sh`
- Modify: rollback/backup helpers touched by current 23.01 update transaction
- Test: add/update install/update transaction tests under `tests/`

**Interfaces:**
- Produces atomic migration from old exposed protocol ports to one TCP/UDP 443 edge.

- [ ] Backup Nginx stream config, protocol runtime configs, UDP-edge config/unit and service states before mutation.
- [ ] Stage private listeners first, validate them, then switch public ownership to the edge services.
- [ ] Add rollback injection tests for failure before edge switch, during edge switch and after edge validation.
- [ ] Ensure rollback never leaves AWG31 and udp-edge both bound to UDP/443.
- [ ] Ensure update preserves all existing client credentials, AWG keys and TLS material.

### Task 8: Firewall, health and diagnostics

**Files:**
- Modify: `install.sh`
- Modify: health/diagnostic modules that expose listener state
- Modify: Connections UI status only where required to show public-vs-private topology
- Test: relevant health/diagnostic tests

**Interfaces:**
- Public firewall allows `80/tcp`, panel TCP port, `443/tcp`, `443/udp` only for the protocol plane.

- [ ] Remove required public allows for legacy protocol ports.
- [ ] Report TCP/443 edge owner, UDP/443 edge owner, private backend health, UDP classifier counters and unknown drops.
- [ ] Redact credentials and keys from all diagnostics.

### Task 9: Full verification and release gate

**Files:**
- Modify: `SOURCE-SHA256SUMS`
- Modify: release documentation/spec status if required

**Interfaces:**
- Produces one exact candidate SHA for live validation.

- [ ] Run focused tests for TCP edge, UDP edge, exports and transactions.
- [ ] Run the complete pytest suite.
- [ ] Refresh `SOURCE-SHA256SUMS` only after production/test files are final.
- [ ] Verify CI on the exact final SHA.
- [ ] On the live server enable every Connection and verify `ss`: Nginx is the only public TCP/443 owner; UDP edge is the only public UDP/443 owner; all protocol backends are private.
- [ ] Validate real external client traffic through AWG31, Reality, XHTTP/Reality, XHTTP/TLS, Hysteria2, Mieru, AnyTLS, TUIC and NaiveProxy.
- [ ] Reboot and repeat listener plus traffic checks.
- [ ] Keep PR #5 draft and unmerged until every live check passes.

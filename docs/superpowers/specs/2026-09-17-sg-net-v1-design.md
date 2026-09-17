# SG-Net/1 v0.1 — Design Specification

Date: 2026-09-17
Status: approved design baseline
Runtime language: Go
Target repository: s-gor/sg-gateway-v23
Target branch: feature/2301-sgnet-integration
Base: dev-02301 @ ced7fe9ca4db6edfd36eb1af54e8d8e61121ae81

## 1. Purpose

SG-Net is a closed transport protocol for the SG ecosystem. It is intended for SG-Gateway, SG Mobile and SG Client only. Third-party interoperability is not a design goal.

Priorities:

1. Minimize stable, externally observable SG-Net-specific protocol fingerprints.
2. High throughput and low connection-establishment overhead.
3. Reliable operation on unstable and mobile networks.
4. Keep SG-Net Core independent enough to support additional standard transports later.

SG-Net does not claim absolute invisibility. The concrete requirement is to avoid a proprietary cleartext handshake, magic bytes, reusable credentials in cleartext, or an unnecessary stable application marker before the protected transport is established.

## 2. Scope of SG-Net/1

Version 1 contains:

- SG-Net Core v1;
- SG-TLS/1 transport;
- TLS 1.3;
- per-device credentials;
- TCP relay;
- UDP relay;
- compact binary framing inside the protected transport;
- multiplexing;
- a bounded pool of physical transport connections;
- keepalive and health state;
- reconnect with bounded backoff;
- short-lived overlapping sessions during physical-network handover;
- IPv4, IPv6 and dual-stack support;
- SG-Gateway, SG Mobile and SG Client integration points.

Deferred from v1:

- SG-H3;
- SG-Auto;
- transparent resurrection of already-broken TCP streams;
- custom cryptography;
- complex traffic-shaping/padding schemes;
- public third-party client support.

## 3. Architecture

Client data path:

`OS TUN -> sing-box -> SG-Net Core -> SG-TLS transport pool -> SG-Net Server -> Internet`

SG Mobile and SG Client retain ownership of TUN, routing, DNS policy and OS integration. SG-Net handles authentication, sessions, relay, multiplexing, transport pooling, keepalive, reconnect and capability negotiation.

SG-Net Server is a separate Go runtime. SG-Gateway remains the control plane only. User traffic must never transit through Python SG-Gateway code.

SG-Net is an independent SG-Gateway Connection/runtime. It is not a Mihomo subprofile and must not share lifecycle with Xray, Mihomo, AWG, AnyTLS, TUIC, NaiveProxy or other runtimes.

## 4. Runtime layout

Recommended server layout:

```text
runtime/sgnet/
  cmd/sgnet-server/main.go
  internal/auth/
  internal/protocol/
  internal/framing/
  internal/session/
  internal/transport/
  internal/relay/
  internal/config/
  internal/health/
```

Installed binary:

`/usr/local/bin/sgnet-server`

Generated config:

`/etc/sg-gateway/sgnet.json`

Systemd unit:

`sg-gateway-sgnet.service`

Local health endpoint should use a Unix socket or loopback-only endpoint, for example:

`/run/sg-gateway/sgnet.sock`

## 5. SG-TLS/1 transport

SG-TLS/1 uses standard TLS 1.3 and standard server-certificate validation.

Before the protected channel exists SG-Net sends no proprietary cleartext handshake, no SG-Net magic bytes and no reusable device credential.

Wire sequence:

`TCP -> TLS 1.3 -> protected SG-Net authentication -> session -> binary multiplexed relay`

No custom cipher, key exchange or certificate-validation mechanism is introduced.

## 6. Device identity and authentication

Each SG device has an independent credential. A shared global SG-Net password is prohibited.

For v1, use a 256-bit random per-device secret and HMAC-SHA256 proof inside the protected TLS session. The secret itself is never transmitted as the authentication message.

The protected authentication handshake carries at least:

- protocol major/minor version;
- device identifier;
- fresh client nonce;
- negotiated capability set;
- authentication proof bound to fresh session material.

The server returns at least:

- fresh session_id;
- negotiated protocol/capabilities;
- bounded session parameters.

Replay protection must reject captured authentication messages. Secret comparisons must be constant-time where applicable.

Deleting/revoking one device credential must not affect other devices.

## 7. Version and capability negotiation

SG-Net/1 initially advertises capabilities such as:

- tcp;
- udp;
- mux.

Unknown optional capabilities are ignored. Unsupported protocol major versions fail explicitly after TLS is established. The user-visible SG-Net profile remains stable across compatible transport evolution.

## 8. Binary framing

The data plane is binary, not JSON.

Logical frame header fields include:

- version/type;
- flags;
- stream_id or association identifier;
- payload length.

Initial logical frame operations:

- OPEN;
- DATA;
- DATAGRAM;
- CLOSE / RESET / half-close semantics;
- SETTINGS / CONTROL;
- PING;
- PONG;
- GOAWAY;
- ERROR.

Exact byte allocation is frozen only after golden-vector tests are written.

## 9. TCP and UDP relay

Each TCP flow uses its own logical stream identifier. Many logical TCP flows may share one physical SG-TLS connection.

UDP remains datagram-oriented. Destination metadata is carried when required. UDP is not converted into one artificial endless byte stream.

Both IPv4 and IPv6 destinations are supported from the first release.

## 10. Bounded connection pool

SG-Net Core maintains a small bounded pool of physical SG-TLS connections. The entire device must not depend on one permanent TCP connection.

The pool owns:

- connection creation;
- health state;
- flow assignment;
- draining;
- replacement;
- backoff;
- hard limits.

Failure of one pool member must not restart the whole VPN or terminate healthy pool members.

## 11. Handover and overlapping sessions

During Wi-Fi/LTE or other physical-network transitions, the same device may temporarily have more than one SG-Net session.

The server distinguishes them using session_id. The new path accepts new flows; the old path drains for a bounded grace period and is then closed.

SG-Net/1 does not promise transparent resurrection of TCP flows that are already broken. Applications reconnect normally. UDP can continue on the new healthy transport path.

On Android, SG-Net integrates with existing physical-network observation, VpnService.protect() and setUnderlyingNetworks(). A physical-network transition alone must not force full TUN/VPN recreation if the runtime remains viable.

## 12. SG-Gateway integration

Create an independent SG-Net Connection with engine/type `sgnet`.

Recommended application structure:

```text
app/sgnet/
  models.py
  service.py
  config.py
  credentials.py
  status.py
```

Host/control integration may use a dedicated module under `hostd/sg_hostd/`.

SG-Gateway responsibilities:

- install/update/remove the Go runtime;
- generate/validate config;
- provision, rotate and revoke device credentials;
- start/stop/restart the dedicated systemd unit;
- expose readiness/runtime health;
- include SG-Net in update transactions;
- include SG-Net state in backup/restore;
- export SG-Net configuration only to SG-controlled clients.

## 13. Connection/API model

SG-Net must behave like a standalone Connection rather than a hidden Mihomo flag.

Expected control surfaces include independent create/read/update/delete/state operations and status reporting for SG-Net. Exact HTTP route naming should follow the existing v23 Connection patterns instead of introducing a parallel API style.

Credential operations require create, rotate and revoke semantics bound to existing device identity records.

## 14. Private SG subscription payload

SG-Net profile delivery is private to SG clients. No public interoperability contract is required for `sgnet://`.

The internal payload needs at least:

- type = sg-net;
- protocol version;
- server endpoint;
- TLS server name;
- device identifier;
- device credential material/reference;
- supported transports/capabilities.

The user should see one profile named `SG-Net`. Future SG-TLS/SG-H3 selection remains internal to that profile.

Secrets must not be emitted into ordinary logs, telemetry or diagnostic exports.

## 15. Atomic runtime configuration

Runtime configuration updates must use staging and atomic replacement:

`generate -> validate -> temporary file -> fsync -> atomic rename -> reload/restart -> health check`

On health failure, restore previous config/binary/service state.

SG-Net runtime updates must participate in the same SG-Gateway update transaction discipline as other production runtimes.

## 16. Health and observability

Local runtime health may expose:

- runtime version;
- protocol version;
- listener state;
- active session count;
- active stream count;
- uptime;
- aggregate authentication failures.

It must never expose reusable credentials or private keys.

## 17. Backup and restore

Backups containing SG-Net must preserve:

- SG-Net Connection settings;
- runtime/server configuration state;
- server identity material when required;
- per-device credential records;
- credential rotation state;
- revocation state.

If v1 stores HMAC device secrets server-side, backup/restore must preserve them securely or restored clients will become invalid.

Old backups without SG-Net must restore successfully and must not create a fake SG-Net Connection.

Restoring SG-Net must not damage unrelated Xray, Mihomo, AWG, AnyTLS, TUIC, NaiveProxy or other Connection state.

## 18. Revocation and rotation

Revoking a device prevents new sessions immediately. Active sessions receive graceful shutdown/GOAWAY semantics followed by a short bounded close grace.

Credential rotation permits a bounded overlap period where old and new device credentials are accepted, after which the old credential is retired.

## 19. Resource and parser safety

Mandatory limits include:

- maximum frame size;
- maximum streams/session;
- maximum sessions/device;
- bounded send/receive queues;
- handshake timeout;
- idle timeout;
- authentication rate limits;
- bounded reconnect backoff.

Malformed lengths or peer input must not trigger unbounded allocation.

## 20. Logging rules

Never log:

- device secret;
- reusable authentication proof;
- TLS private key;
- raw subscription credential.

Opaque identifiers such as device_id, session_id and stream_id may be logged when useful.

## 21. Packet-level acceptance

Release validation must include packet capture checks confirming:

- no proprietary SG-Net cleartext handshake before TLS protection;
- no device credential in cleartext;
- no deliberate fixed SG-Net application marker outside the protected channel;
- no fallback to a proprietary plaintext protocol after errors;
- no constant custom padding scheme in v1.

This is a concrete fingerprint-minimization requirement, not a claim of absolute undetectability.

## 22. Testing strategy

Before production acceptance:

- unit tests for framing and state machines;
- golden vectors for all SG-Net/1 frames and handshake structures;
- negative auth/revocation/replay tests;
- malformed-frame tests;
- fuzz tests for frame/handshake parsers;
- TCP relay integration tests;
- UDP relay integration tests;
- IPv4/IPv6/dual-stack tests;
- multi-stream tests;
- multi-connection pool tests;
- forced pool-member failure tests;
- handover simulation;
- backup/restore tests;
- update/rollback tests;
- Android end-to-end tests;
- Windows end-to-end tests;
- packet-capture regression checks;
- load/resource-limit tests.

A successful connection alone is not release acceptance.

## 23. Implementation stages

1. Go protocol/core package: framing, parser, state machine, auth primitives, relay abstractions.
2. SG-TLS server/client transport with local integration tests.
3. Golden vectors, replay/negative/fuzz/resource tests.
4. SG-Gateway standalone Connection and runtime lifecycle.
5. Atomic update/rollback integration.
6. Backup/restore integration.
7. Private SG subscription export.
8. SG Client integration.
9. SG Mobile integration with protect()/underlying-network handover.
10. Real-network validation and packet-capture acceptance.

SG-H3 and SG-Auto begin only after SG-TLS/1 is stable in production-like testing.

## 24. Definition of success

SG-Net/1 v0.1 is accepted only when SG-Gateway can provision an independent SG-Net Connection, SG Mobile and SG Client can authenticate independently revocable devices, TCP and UDP work over IPv4 and IPv6, connection-pool failures do not unnecessarily kill the VPN, realistic network handover works without uncontrolled reconnect storms, backup/update rollback preserve state, malformed input stays bounded, and packet capture shows no deliberate proprietary SG-Net cleartext handshake before the protected transport is established.

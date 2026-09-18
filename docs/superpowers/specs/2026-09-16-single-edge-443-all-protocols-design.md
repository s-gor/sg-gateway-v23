# SG-Gateway 23.01 All-Protocol Single Edge 443 Design

## Goal

All client-facing SG-Gateway protocols MUST advertise and use public port `443` on one public IPv4/IPv6 address. The panel remains separate on TCP `63443`. No internal implementation port may leak into client links, QR payloads, subscriptions, generated configs, documentation examples, or status summaries intended to describe public endpoints.

## Public ingress contract

Only two sockets are public protocol ingress:

- `TCP/443` — one TCP edge owner.
- `UDP/443` — one UDP edge owner.

The panel remains on `TCP/63443`. HTTP/ACME remains on `TCP/80`.

Every protocol backend uses a private internal listener. TCP backends bind loopback. UDP backends bind loopback or another non-public local address owned by SG-Gateway. The public edge forwards traffic to those internal listeners.

## Protocol matrix

### TCP/443

- Xray Reality TCP -> internal `127.0.0.1:10443`, selected by REALITY SNI.
- XHTTP/Reality -> internal `127.0.0.1:10444`, selected by XHTTP Reality SNI.
- TLS hub -> internal Caddy `127.0.0.1:10447`, selected by the configured SG-Gateway HTTPS domain. Caddy then dispatches:
  - XHTTP/TLS path `/sg-xhttp-tls` -> `127.0.0.1:10445` over h2c.
  - NaiveProxy -> handled by Caddy forward_proxy on the same TLS listener.
  - ordinary browser HTTPS -> placeholder HTTP `127.0.0.1:10446`.
- AnyTLS and Mieru/TCP must also be reachable from public TCP/443 without exposing their internal ports. They need distinct edge classification that is deterministic before forwarding. If a protocol cannot be classified safely on the shared TCP edge with its current wire format, the implementation must change its public-facing encapsulation/termination model rather than expose a second public TCP port.
- Unknown SNI must continue to reach the TLS placeholder and must not be sent to a VPN backend accidentally.

### UDP/443

The single public UDP owner is a dedicated SG-Gateway UDP dispatcher. Protocol runtimes do not bind public UDP/443 directly.

The dispatcher must distinguish and forward:

- AmneziaWG 3.1 -> private AWG31 backend.
- Hysteria2 -> private Hysteria2 backend.
- TUIC v5 -> private TUIC backend.
- Mieru/UDP -> private Mieru backend when Mieru UDP is selected.

The dispatcher must be session-aware: after the first packet classifies a flow, subsequent datagrams for that 5-tuple follow the same backend until expiry. Backend replies must return through the dispatcher so the client continues to see the public source `:443`.

No protocol backend may use SO_REUSEPORT competition on public UDP/443 as a substitute for classification. Hash-based socket distribution does not understand protocol semantics and is therefore not acceptable.

## UDP classification requirements

Classification must be based only on deterministic wire-level properties that can be validated for the exact runtime versions shipped by SG-Gateway. Guessing by packet length alone is not sufficient unless paired with a protocol-specific invariant and regression fixtures.

The implementation must include captured/synthetic first-flight fixtures for AWG31, Hysteria2, TUIC and Mieru/UDP and unit tests proving that each fixture selects only its intended backend and that malformed/unknown datagrams are dropped rather than misrouted.

If two enabled UDP protocols cannot be classified unambiguously from their initial client datagrams, the implementation MUST NOT pretend that both can safely share UDP/443. In that case the design must introduce a supported discriminator (for example a protocol-supported obfuscation or encapsulation marker) and update both server runtime generation and client exports accordingly. Public fallback to another port is prohibited by the product requirement.

## Runtime ownership

- Nginx owns public TCP/443.
- A new managed SG-Gateway UDP edge service owns public UDP/443.
- AWG31 must move from `0.0.0.0:443/[::]:443` to its private backend listener.
- Xray Hysteria2 must move from public UDP/8446 to a private backend listener.
- TUIC must move from its current public UDP listener to a private backend listener.
- Mieru/UDP must move from its current public listener to a private backend listener.
- Mieru/TCP and AnyTLS must not remain on public 2099/8443/9443-style ports once the shared TCP edge is complete.

Internal port numbers are implementation details and may be changed if needed to avoid collisions. The only stable client-facing port is `443`.

## Client export contract

Every enabled client-facing protocol must advertise public port `443`:

- AWG31 config and URI endpoint -> `host:443`.
- Reality -> `host:443`.
- XHTTP/Reality -> `host:443`.
- XHTTP/TLS -> `host:443`.
- Hysteria2 -> `host:443`.
- Mieru -> `host:443`.
- AnyTLS -> `host:443`.
- TUIC v5 -> `host:443`.
- NaiveProxy -> `host:443`.

This applies to direct links, QR, Mihomo YAML, SG Client subscription output and any backup-restored credentials whose public endpoint is regenerated.

## Installation and update contract

Clean install and update must:

1. stage new private backend listeners;
2. validate runtime configs;
3. install/validate the TCP edge and UDP dispatcher;
4. switch public ownership of TCP/443 and UDP/443 atomically;
5. verify listeners and protocol health;
6. roll back all changed runtime configs/services/firewall state if any step fails.

The update path must preserve credentials and keys. Rollback must restore the prior listener topology and service states without leaving two services competing for UDP/443.

## Firewall contract

External allow rules required by the protocol plane are:

- `443/tcp`
- `443/udp`
- `80/tcp` for HTTP/ACME
- panel `63443/tcp` (or the configured panel port)

Legacy public protocol ports such as `2099`, `8443`, `8446`, `9443`, `10443`, `10444`, `10445`, `10447` must not be required by clients and must not be opened as public protocol ingress.

## Observability

The panel/diagnostics must separately report:

- public edge ownership (`TCP/443`, `UDP/443`);
- each backend protocol and its private listener;
- dispatcher classification counters per UDP protocol;
- unknown/dropped UDP datagrams;
- last successful edge validation.

No secrets, keys, passwords or complete client links may appear in diagnostics.

## Acceptance criteria

1. With every Connection enabled, `ss -lntup` shows only Nginx on public TCP/443 and only the SG-Gateway UDP edge on public UDP/443.
2. AWG31, Hysteria2, TUIC and Mieru/UDP backends are not bound to public addresses.
3. All TCP protocol backends are private and no client link advertises an internal port.
4. Direct exports, QR and subscriptions contain `:443` for every enabled protocol.
5. Live external clients successfully pass traffic through every enabled protocol.
6. Reboot preserves the topology and all enabled protocol services return automatically.
7. Clean install on Ubuntu 24.04 produces the same topology without manual patching.
8. Update from the current 23.01 branch migrates an existing server transactionally.
9. Rollback restores the pre-update state after injected failures.
10. CI includes regression tests for public-port invariants, UDP classification, export rewriting, install/update/rollback and reboot/service enablement contracts.
11. PR #5 remains draft and MUST NOT be merged until all acceptance criteria above are satisfied on the live server.

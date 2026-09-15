# SG-Gateway 23.01 — Single Edge 443 design

## Scope

This design applies only to `s-gor/sg-gateway-v23`, branch `feat/2301-single-edge-443`. `sg-gateway-v22` is frozen and must not be changed. SG-InfoSec is explicitly out of scope.

## Public listener contract

- TCP/22: SSH.
- TCP/80: HTTP placeholder and ACME HTTP-01.
- TCP/443: shared SG-Gateway protocol edge plus ordinary HTTPS placeholder.
- TCP/63443: SG-Gateway panel HTTPS. The panel is deliberately outside the shared 443 edge.
- UDP/443: AWG3.1 when enabled. It is independent from TCP/443.
- Hysteria2 remains on its dedicated UDP listener (8446 by default).

No migrated Xray or NaiveProxy backend may expose a secondary public TCP listener.

## TCP/443 routing model

Nginx `stream` owns public TCP/443 and performs only TLS ClientHello/SNI inspection with `ssl_preread`.

Loopback backends:

- Reality TCP -> `127.0.0.1:10443`.
- XHTTP Reality -> `127.0.0.1:10444`, using its dedicated Reality SNI.
- Gateway TLS SNI -> shared Caddy TLS hub on `127.0.0.1:10447`.
- Unknown SNI -> internal Nginx TLS placeholder on `127.0.0.1:7444`.

The shared Caddy TLS hub terminates ordinary gateway TLS and provides three behaviors on one listener:

- NaiveProxy forward proxy when credentials exist.
- XHTTP TLS path `/sg-xhttp-tls` -> h2c `127.0.0.1:10445`.
- All ordinary browser HTTPS -> loopback HTTP placeholder `127.0.0.1:10446`.

The panel is not a Caddy fallback and is not reachable through the shared 443 route. Nginx terminates panel TLS directly on public TCP/63443 and proxies the application backend on `127.0.0.1:18080`.

## Clean-install TLS bootstrap

The shared Caddy TLS hub is infrastructure for XHTTP TLS and HTTPS fallback, not merely an optional NaiveProxy listener. Therefore HTTPS setup must start it even when there are zero NaiveProxy users.

After Certbot has produced a certificate, `configure-panel-access.sh`:

1. renders the Nginx stream and HTTP/HTTPS listeners;
2. configures the shared TLS-edge domain and certificate in the NaiveProxy connection state;
3. validates and starts Caddy on loopback `10447`, including the zero-user case;
4. validates Nginx and reloads it;
5. verifies HTTP/80 placeholder, HTTPS/443 placeholder, and panel HTTPS on the configured panel port (default 63443);
6. applies the remaining client runtimes.

Certificate refresh repeats the Caddy bootstrap before endpoint verification so the shared TLS hub receives renewed certificate material before acceptance.

## Addressing and exports

Migrated TCP protocol client exports advertise the public host on port 443. Internal ports 10443/10444/10445/10446/10447 and 7444 are implementation details and must not leak into client links.

The panel URL uses the configured public panel port, default `https://domain:63443/`.

## Firewall contract

Public SG-Gateway requirements for this slice are TCP/22, TCP/80, TCP/443, TCP/63443, UDP/443 for AWG3.1, and the dedicated Hysteria2 UDP port when enabled. Old migrated secondary TCP protocol ports are not public ingress.

## Acceptance

Automated tests and CI must prove that migrated TCP backends bind to loopback, the panel remains separate on 63443, shared 443 routes the gateway TLS SNI to Caddy, XHTTP TLS and NaiveProxy export public 443, ordinary HTTPS on 443 serves only the placeholder, the shared TLS hub bootstraps on a clean install with zero NaiveProxy users, AWG3.1 may independently use UDP/443, Hysteria2 remains separate UDP, source-integrity checks pass, and the full existing test suite remains green.

`main` is not updated until live-server acceptance of the verified `dev-02301` candidate.

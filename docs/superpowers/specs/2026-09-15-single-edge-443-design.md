# SG-Gateway 23.01 — Single Edge 443 design

## Scope

This design applies only to `s-gor/sg-gateway-v23`, branch `feat/2301-single-edge-443`. `sg-gateway-v22` is frozen and must not be changed. SG-InfoSec is explicitly out of scope for this change.

## Goal

Collapse SG-Gateway TCP-facing protocols onto one public TCP entrypoint, port 443, while keeping protocol runtimes isolated on loopback listeners. UDP remains independent and is not multiplexed by the TCP edge in this phase.

## Public listener contract

- TCP/443: single SG-Gateway edge listener.
- UDP/443: reserved for AWG3.1 when enabled; TCP and UDP may share the same numeric port because they are different transports.
- Hysteria2 remains on its existing UDP listener in this phase.
- No Xray/NaiveProxy backend may bind a secondary public TCP port once migrated to the single edge.

## TCP routing model

Nginx `stream` owns TCP/443 and uses TLS ClientHello/SNI inspection (`ssl_preread`) only; it does not terminate Reality traffic.

Backends bind to `127.0.0.1` only:

- Reality TCP -> dedicated loopback Xray listener.
- XHTTP Reality -> dedicated loopback Xray listener.
- XHTTP TLS -> dedicated loopback Xray listener.
- NaiveProxy -> dedicated loopback backend listener.
- HTTPS/panel front door, when exposed through the edge, -> dedicated loopback TLS/HTTP backend.

Routing is deterministic. Reality traffic remains passthrough. TLS protocols that use an explicit server name are routed by SNI. Unknown SNI falls back to the configured Reality listener so the existing Reality camouflage behavior is preserved.

## Addressing and links

Client exports for migrated TCP protocols advertise the server public host and public port 443. Internal listener ports remain implementation details and must not leak into generated client links or UI metadata.

The Xray settings model may continue storing per-profile internal listener ports, but public-port validation must no longer reject profiles simply because multiple migrated TCP profiles share public 443: uniqueness applies to loopback listener ports, not the public edge port.

## Installation/update behavior

Clean install and update must create the edge configuration atomically:

1. Render backend configs bound to loopback.
2. Validate each backend configuration before activation.
3. Render the Nginx stream map/listener.
4. Run `nginx -t`.
5. Only then reload/restart affected services.

If validation fails, the previous working configuration remains active.

The installer must not alter SG-InfoSec configuration or certificates as part of this feature.

## Firewall contract

After migration, SG-Gateway no longer requires public firewall openings for migrated secondary TCP ports such as 8444/8445/9443. TCP/443 remains public. UDP rules remain protocol-specific.

## Compatibility

Existing clients that use old secondary TCP ports are not silently rewritten by this first feature branch. The server-side migration and new generated links target 443. Backward-compatibility listeners, if needed, must be a separately approved transition step rather than hidden permanent listeners.

## Tests / acceptance

Automated tests must prove:

- exactly one SG-Gateway public TCP/443 edge listener is rendered;
- migrated backends bind only to 127.0.0.1;
- Reality remains passthrough and is the unknown-SNI fallback;
- XHTTP Reality/XHTTP TLS/NaiveProxy links advertise public port 443;
- internal listener ports do not appear in exported links;
- Xray profile validation allows shared public 443 while keeping loopback listener ports unique;
- migrated secondary public TCP firewall rules are removed;
- Hysteria2 UDP behavior is unchanged;
- AWG3.1 UDP may use numeric port 443 independently of TCP/443;
- full existing CI remains green.

## First implementation slice

The first slice implements the TCP edge and migrates Xray TCP profiles to loopback + public 443. NaiveProxy follows in the same feature branch only after the Xray edge tests are green. This keeps failures attributable and avoids a multi-runtime cutover in one unverified change.

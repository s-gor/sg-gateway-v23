# SG-Gateway 23.01 Bootstrap Design

## Purpose

Create a clean SG-Gateway v23 code line in `s-gor/sg-gateway-v23` without modifying `s-gor/sg-gateway-v22` in any way. The new repository starts from the currently proven 22.08 runtime behavior, but receives a new version identity, a clean CI/test contract, and a new architectural development line for 23.01.

## Non-negotiable isolation rule

`sg-gateway-v22` is read-only for this project. No commits, branch moves, tags, releases, workflow changes, file updates, pull requests, or force pushes may be made to v22 while building v23.

The v22 repository may only be read as a source reference.

## Source baseline

The runtime behavior copied into v23 must include the two real-server-verified fixes already present in the v22 22.08 line:

1. Xray recovery upgrade from an older incompatible configuration must install the candidate Xray, regenerate the Xray config under the new binary, validate the regenerated config, and restore both old binary and old config on failure.
2. NaiveProxy's `protocol_ready()` compatibility layer must forward `xray_state`, so Reality TCP, XHTTP Reality, XHTTP TLS, and Hysteria2 client links can all be generated correctly.

The public-install pinning commit from v22 is not a runtime source requirement. v23 must have its own installation identity and must not retain hard-coded 22.08 source SHAs.

## Repository history model

The v23 repository is a clean line, not a forked continuation of v22 history.

- Do not import v22 Git history.
- Do not import v22 tags or releases.
- Do not import failed Actions history.
- The first code bootstrap commit in v23 must be independently understandable as the 23.01 baseline.
- Historical 22.08 publication documents may be omitted unless needed as migration reference.

## Version identity

The initial v23 development identity is:

- Product line: SG-Gateway v23
- Version: `0.1.0-023.01`
- Development channel: `dev-02301`
- Initial build identity: `MAIN-02301-DEV`

No `stable-02208`, `022.08`, or pinned v22 installation SHA may remain in active v23 installation/update commands.

## Supported runtime scope for the clean baseline

The 23.01 baseline keeps the active runtime families needed for the next architecture:

- AWG 3.1
- Xray Reality TCP
- Xray XHTTP Reality
- Xray XHTTP TLS
- Xray Hysteria2
- Hysteria2 Salamander/Gecko modes provided by Xray
- NaiveProxy
- Mihomo/Mieru functionality currently used by the product
- Panel, HostD, backup/restore, clients, subscriptions, maintenance, routing, diagnostics, and update safety required by the working 22.08 product

Retired AWG2 and AWG3.0 are not part of the active v23 product contract.

Historical database/backup compatibility data may remain where required for safe migration or restore, but the active UI, installer, runtime readiness checks, and current tests must not require AWG2 or AWG3.0 to exist.

## Test and CI reset

The current v22 suite contains stale contracts that intentionally describe removed product behavior. v23 must not inherit those failures as accepted debt.

During bootstrap:

- Copy tests that still describe supported behavior.
- Rewrite or remove tests whose only purpose is retired AWG2/AWG3.0 UI/runtime behavior.
- Remove version/publication assertions tied to 021xx/022xx history when they do not describe current behavior.
- Keep or adapt tests for backup/restore compatibility where retired records are intentionally preserved.
- Keep focused tests for both real-server-verified Xray fixes.
- Source-integrity verification must be regenerated for the v23 tree, not copied with stale hashes.
- `main` must reach a clean green bootstrap CI before Single Edge 443 implementation begins.

A failing test may be retained only if it represents a real current defect that is explicitly accepted into the v23 bootstrap plan; stale historical expectations are not acceptable as the reason for a red baseline.

## Bootstrap branch strategy

The initial repository bootstrap may be built directly as the first coherent v23 baseline because the repository is new and empty, but architectural product work must not be developed directly on `main` after bootstrap.

After the green 23.01 baseline is established:

- `main` = clean v23 bootstrap baseline
- feature branch = `feat/2301-single-edge-443`

The Single Edge architecture is reviewed and tested on the feature branch before promotion.

## Single Edge 443 target architecture

The 23.01 architectural target is to minimize externally visible service ports.

### TCP edge

All supported external TCP/TLS entry points should converge on TCP 443 through an L4 edge router.

The edge router must route by information available without terminating protocols that require passthrough. Internal applications listen on loopback addresses, for example:

- `127.0.0.1:<internal-port>` — Xray Reality TCP
- `127.0.0.1:<internal-port>` — XHTTP TLS
- `127.0.0.1:<internal-port>` — NaiveProxy
- `127.0.0.1:<internal-port>` — HTTPS Panel

Exact internal ports are assigned during the Single Edge implementation plan and must not collide with existing services.

Reality traffic must remain TCP passthrough. The front layer must not terminate Reality TLS semantics.

SNI-capable TLS services may be routed at L4 by SNI when protocol behavior permits it.

### UDP edge

TCP 443 and UDP 443 may coexist, but AWG 3.1 and Hysteria2 cannot be multiplexed by ordinary TLS SNI because AWG 3.1 is raw WireGuard-family UDP.

The implementation must explicitly choose one owner for UDP 443.

Preferred initial policy:

- TCP 443: L4 edge for TCP/TLS families
- UDP 443: AWG 3.1
- Hysteria2: separate explicitly managed UDP port

This policy may be changed only by an explicit design amendment before implementation.

## Firewall target

The desired external exposure after Single Edge work is approximately:

- SSH TCP port, when administration requires it
- TCP 443 for the shared edge
- UDP 443 for AWG 3.1 under the preferred policy
- one explicitly documented Hysteria2 UDP port when Hysteria2 remains enabled externally

All internal TCP service listeners used behind the edge should bind to loopback unless a protocol has a documented reason not to.

## Connection readiness model

v23 must keep the distinction between stored client access and server-side runtime readiness.

A restored credential or subscription record does not itself prove that the corresponding server Connection is operational. Client exports should continue to report readiness accurately rather than silently producing unusable profiles.

The 23.01 work should preserve this distinction and may make it more explicit, but a broad redesign of backup/restore is not part of the bootstrap itself.

## Installation and update contract

v23 must have its own installer/update identity.

- Clean Install must source v23, not v22.
- Update must source the selected v23 channel.
- No active command may point to `sg-gateway-v22`.
- No active command may pin a v22 commit SHA.
- Update safety and rollback behavior inherited from the working product must remain covered by tests.
- Clean install must be tested independently from update.

## Migration discipline

The bootstrap is a product-line migration, not a simultaneous rewrite.

Do not combine these into one unreviewable change:

1. source-tree bootstrap/version reset;
2. stale-test cleanup and clean CI baseline;
3. Single Edge 443 architecture;
4. later UI/Connections redesign.

Each stage must leave a coherent, testable state.

## Acceptance criteria for the v23 bootstrap

The bootstrap is complete only when all of the following are true:

1. All writes occurred only in `s-gor/sg-gateway-v23`.
2. v23 contains the working supported runtime behavior from the accepted 22.08 product, including both current Xray fixes.
3. Version and channel identity are `0.1.0-023.01` / `dev-02301`.
4. Active install/update commands reference only v23.
5. Active product contract contains AWG 3.1 but not AWG2/AWG3.0.
6. Historical compatibility data is retained only where required for migration/restore safety.
7. Source-integrity data is regenerated for the v23 tree.
8. Bootstrap CI is green with no accepted stale-test failures.
9. `main` is the green bootstrap baseline before Single Edge work begins.
10. Single Edge development proceeds on `feat/2301-single-edge-443`.

## Out of scope for bootstrap

The following are intentionally deferred until after the green v23 baseline:

- final L4 edge implementation;
- exact internal port allocation;
- UI cosmetic redesign;
- broad Connections page redesign;
- new protocol families;
- changes to v22 releases, tags, branches, or installation commands.

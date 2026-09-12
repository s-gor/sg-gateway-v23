# SG-Gateway 23.01 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a clean, independently versioned SG-Gateway 23.01 baseline in `s-gor/sg-gateway-v23` from the proven v22 runtime snapshot, with v23-only install/update identity and a green CI baseline before Single Edge 443 work begins.

**Architecture:** Treat `s-gor/sg-gateway-v22` as an immutable read-only source at exact runtime SHA `6d8b07125289566a6e8a7ba206094d8969e92125` (the real-server-verified runtime point containing both Xray fixes). Seed v23 through a one-time GitHub Actions bootstrap job that checks out v22 read-only, copies the supported source tree into a v23 bootstrap branch, rewrites product/repository/version identity, and removes publication-only v22 artifacts. Then repair the test/CI contract on the bootstrap branch until fully green, merge the coherent baseline to `main`, and only then create `feat/2301-single-edge-443`.

**Tech Stack:** Python, Flask/HostD, shell deployment scripts, systemd/runtime assets, pytest, GitHub Actions, GitHub Git data/contents APIs.

**Spec:** `docs/superpowers/specs/2026-09-12-sg-gateway-2301-bootstrap-design.md`

## Global Constraints

- `s-gor/sg-gateway-v22` is read-only. No writes, branch moves, tags, PRs, releases, workflow edits, or force pushes.
- Source runtime snapshot is exactly `6d8b07125289566a6e8a7ba206094d8969e92125`; the later v22 install-pin publication commit is not the runtime source.
- v23 version is `0.1.0-023.01`.
- v23 development channel is `dev-02301`.
- Initial build identity is `MAIN-02301-DEV`.
- Active runtime contract keeps AWG 3.1 and supported Xray/NaiveProxy/Mieru/Mihomo behavior; AWG2 and AWG3.0 are retired from the active product contract.
- Historical AWG2/AWG3.0 data may remain only where restore/migration compatibility requires it.
- Active install/update commands must reference only `s-gor/sg-gateway-v23` and must not contain a pinned v22 SHA.
- The Xray recovery-upgrade regression and NaiveProxy `xray_state` forwarding regression must remain covered.
- `main` must have a green bootstrap CI before `feat/2301-single-edge-443` is created.

---

### Task 1: Seed the v23 source tree without writing to v22

**Files:**
- Create temporarily: `.github/workflows/bootstrap-from-v22.yml`
- Produce on branch `bootstrap/2301-source`: working source tree copied from v22 runtime SHA

**Interfaces:**
- Consumes: public read access to `s-gor/sg-gateway-v22@6d8b07125289566a6e8a7ba206094d8969e92125`.
- Produces: `bootstrap/2301-source` in v23 containing the supported source snapshot and existing v23 design/plan docs.

- [ ] **Step 1: Add the one-time bootstrap workflow**

The workflow must run in `s-gor/sg-gateway-v23`, request `contents: write`, check out v23 and the exact v22 SHA into separate directories, create/update `bootstrap/2301-source`, copy source files while preserving the v23 `docs/superpowers/` design/plan files, and never push to v22.

- [ ] **Step 2: Exclude historical publication-only artifacts from the copy**

Do not import v22 Git history, tags, releases, Actions history, `PUBLICATION-02112.md`, `PUBLICATION-02204.md`, `PUBLICATION-02206.md`, `PUBLICATION-02208.md`, or obsolete release workflows whose only purpose is a v22 release line.

- [ ] **Step 3: Verify branch provenance**

Verify `bootstrap/2301-source` exists only in v23 and that `sg-gateway-v22` branch heads/ruleset are unchanged.

- [ ] **Step 4: Remove the one-time bootstrap mechanism after it has produced the branch**

The finished baseline must not depend on a permanent workflow that recopies v22.

---

### Task 2: Reset product, repository, installer, and update identity to v23

**Files:**
- Modify: `VERSION`
- Modify: `DEVELOPMENT-VERSION`
- Modify: `BUILD-ID`
- Modify: `README.md`
- Modify: `deploy/install-from-github.sh`
- Modify: `deploy/update-from-github.sh`
- Modify: `deploy/update-from-github-core.sh`
- Modify: `deploy/uninstall-from-github.sh`
- Modify: `deploy/GITHUB-COMMANDS.md`
- Modify or replace: release/update workflow files retained under `.github/workflows/`
- Test: add `tests/test_2301_repository_identity.py`

**Interfaces:**
- Consumes: seeded source tree from Task 1.
- Produces: a tree whose active GitHub source identity is exclusively `s-gor/sg-gateway-v23` and channel `dev-02301`.

- [ ] **Step 1: Write failing identity tests**

The test must assert:

```python
from pathlib import Path


def test_2301_version_identity():
    assert Path("VERSION").read_text().strip() == "0.1.0-023.01"
    assert Path("DEVELOPMENT-VERSION").read_text().strip() == "0.1.0-023.01-dev"
    assert Path("BUILD-ID").read_text().strip() == "MAIN-02301-DEV"


def test_active_commands_use_v23_only():
    paths = [
        Path("README.md"),
        Path("deploy/GITHUB-COMMANDS.md"),
        Path("deploy/install-from-github.sh"),
        Path("deploy/update-from-github.sh"),
        Path("deploy/update-from-github-core.sh"),
        Path("deploy/uninstall-from-github.sh"),
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "s-gor/sg-gateway-v23" in text
    assert "s-gor/sg-gateway-v22" not in text
    assert "stable-02208" not in text
    assert "6d8b07125289566a6e8a7ba206094d8969e92125" not in text
```

- [ ] **Step 2: Run identity tests and confirm they fail on the imported snapshot**

Run: `pytest -q tests/test_2301_repository_identity.py`

Expected: FAIL on v22 version/repository/channel strings.

- [ ] **Step 3: Rewrite identity minimally**

Set:
- `VERSION` → `0.1.0-023.01`
- `DEVELOPMENT-VERSION` → `0.1.0-023.01-dev`
- `BUILD-ID` → `MAIN-02301-DEV`
- GitHub repository constants/URLs → `s-gor/sg-gateway-v23`
- active development branch/channel → `dev-02301`

Do not redesign installer/update behavior in this task.

- [ ] **Step 4: Run identity tests again**

Run: `pytest -q tests/test_2301_repository_identity.py`
Expected: PASS.

---

### Task 3: Preserve the two accepted Xray regressions

**Files:**
- Preserve/adapt: `hostd/sg_hostd/xray_update_runtime.py`
- Preserve/adapt: `app/naiveproxy/integration.py`
- Preserve/adapt: `tests/test_preview31_xray_updates.py`
- Rename/adapt: `tests/test_naiveproxy_xray_state_forwarding_02208.py` → `tests/test_naiveproxy_xray_state_forwarding_2301.py`

**Interfaces:**
- Consumes: the exact runtime behavior verified on the real v22 server.
- Produces: v23 regression protection for Xray recovery update and Xray client-card generation through NaiveProxy integration.

- [ ] **Step 1: Verify the Xray recovery test set**

Run: `pytest -q tests/test_preview31_xray_updates.py`
Expected: all tests PASS.

- [ ] **Step 2: Adapt only historical naming in the NaiveProxy forwarding test**

Keep assertions requiring:

```python
"def protocol_ready(client, kind: str, device=None, *, xray_state=None) -> bool:"
"return original_protocol_ready(client, kind, device, xray_state=xray_state)"
```

- [ ] **Step 3: Run the forwarding regression**

Run: `pytest -q tests/test_naiveproxy_xray_state_forwarding_2301.py`
Expected: PASS.

---

### Task 4: Reset the active AWG contract and remove stale v22-only tests

**Files:**
- Review: `tests/`
- Review: panel/templates/static tests and runtime tests mentioning AWG2/AWG3.0
- Preserve compatibility tests that intentionally verify restore/migration handling of historical records
- Add: `tests/test_2301_active_protocol_contract.py`

**Interfaces:**
- Consumes: imported supported code and existing test suite.
- Produces: a current product contract where AWG 3.1 is active and AWG2/AWG3.0 are not required by UI/runtime readiness/current install behavior.

- [ ] **Step 1: Add the current-contract test**

The test must establish that current user-facing/runtime contract includes AWG 3.1 and does not require AWG2/AWG3.0 assets, labels, services, or seed state.

- [ ] **Step 2: Run the full test suite to capture the initial v23 failure inventory**

Run: `pytest -q`
Record every failing test by category.

- [ ] **Step 3: Classify failures**

For each failure classify as exactly one of:
1. stale retired AWG2/AWG3.0 contract;
2. stale v21/v22 version/publication/install identity;
3. test monkeypatch/signature drift against current supported code;
4. real current product defect.

- [ ] **Step 4: Remove or rewrite only stale expectations**

Do not delete a failing test merely to obtain green CI. Preserve tests for current supported behavior and historical restore compatibility.

- [ ] **Step 5: Fix current-code/test interface drift where behavior is still supported**

Examples already known from v22 include monkeypatches using obsolete signatures around `list_connections`, `_xray_profile`, and connection settings. Update tests or compatibility seams according to the current public function contract; do not restore retired behavior just to satisfy old tests.

- [ ] **Step 6: Re-run full pytest**

Run: `pytest -q`
Expected: zero failures before proceeding.

---

### Task 5: Rebuild source integrity and v23 CI

**Files:**
- Regenerate: `SOURCE-SHA256SUMS`
- Modify: `.github/workflows/ci.yml`
- Remove/replace obsolete `022xx`-specific workflows
- Add/adapt v23 clean-install/update smoke contracts as appropriate

**Interfaces:**
- Consumes: the cleaned v23 tree.
- Produces: deterministic source-integrity verification and a CI workflow that represents current v23 behavior only.

- [ ] **Step 1: Regenerate source hashes from the actual v23 tree**

Do not manually edit individual checksum lines. Generate the manifest deterministically from the tracked production/test source set used by the integrity verifier.

- [ ] **Step 2: Run source-integrity verification locally/in CI**

Expected: every tracked entry verifies and no stale v22-only file is required.

- [ ] **Step 3: Update CI naming/branch assumptions to v23**

Remove assumptions about `dev-02206`, `stable-02208`, `02204`, `02207`, or `02208` where they are only release-line history.

- [ ] **Step 4: Run/observe CI on the exact bootstrap SHA**

Acceptance: syntax, manifest, source integrity, focused Xray regressions, and full pytest all PASS on one exact commit SHA.

---

### Task 6: Promote the green bootstrap baseline and open the architecture branch

**Files:**
- No product-code changes beyond the already reviewed bootstrap tree.

**Interfaces:**
- Consumes: exact green bootstrap SHA from Task 5.
- Produces: `main` as the clean SG-Gateway 23.01 baseline and `feat/2301-single-edge-443` as the only branch for the next architecture stage.

- [ ] **Step 1: Review bootstrap diff for repository isolation**

Verify there are no active references that would cause install/update/publish operations to target v22.

- [ ] **Step 2: Verify v22 is unchanged**

Read and compare the v22 frozen branch/ruleset state. No write operation is permitted.

- [ ] **Step 3: Promote the exact green bootstrap commit to v23 `main`**

Do not promote a different untested SHA.

- [ ] **Step 4: Create `feat/2301-single-edge-443` from the green v23 `main` SHA**

Single Edge 443 implementation begins only after this point.

- [ ] **Step 5: Record the baseline SHA in the project handoff**

The handoff must state the exact v23 main SHA and confirm v22 remained untouched.

# CI/CD Balanced Design (2026-02-12)

## Context

This repository currently has four GitHub Actions workflows:

1. `CI` for backend/frontend quality and PR Docker build checks.
2. `Build and Push Images` for GHCR image publishing.
3. `Teacher E2E`.
4. `Mobile Session Menu E2E`.

Recent runs show a critical consistency gap: image publishing can succeed on `main` even when `CI` fails for the same commit. For demo-focused delivery, this causes avoidable confusion and weakens trust in artifacts.

This design intentionally prioritizes strong, stable CI over full deployment automation. The project does not require staging/prod auto-deploy at this stage.

## User-Aligned Decisions

Confirmed constraints and preferences:

1. No deployment pipeline is required now; focus on CI.
2. CI strictness level is "balanced": quality checks + smoke E2E + Docker build checks.
3. Image publishing remains automatic, but must be gated by CI success on `main`.
4. Release tags (`v*`) should also publish automatically.

## Current-State Assessment

### Strengths

1. Good baseline split between backend and frontend quality checks.
2. Full backend pytest suite is executed in CI.
3. PR-level Docker build validation already exists.
4. E2E artifacts (report/results) are uploaded for debugging.

### Gaps

1. **P0: artifact consistency risk**
   - `Build and Push Images` and `CI` both run independently on `push main`.
   - Result: failed CI can still publish fresh `latest` and `sha-*` image tags.

2. **P1: gate fragmentation**
   - E2E checks are isolated in separate workflows and are not guaranteed branch-protection gates for every PR path.
   - Current triggers focus mainly on `frontend/**`, which misses some backend-induced regressions.

3. **P1: CD naming vs actual behavior**
   - The project has image publication automation, but no environment promotion/deploy controls.
   - This is acceptable for now, but should be explicitly documented as "artifact publishing only."

4. **P2: quality hardening opportunities**
   - Static checks are partly targeted instead of broad critical-path coverage.
   - No explicit coverage fail-under threshold in main CI gate.

## Target State (Balanced CI, No Auto-Deploy)

### Principle

`main` should represent "demo-ready quality."  
Publishing artifacts is allowed only when this quality bar is met.

### Workflow Topology

1. Keep `CI` as the primary required gate for PR and `main`.
2. Add a `smoke-e2e` job into main CI (or reusable sub-workflow called by CI).
3. Keep full E2E workflows as supplementary signal (non-blocking by default, unless later promoted).
4. Change image publishing triggers to:
   - CI-success-driven publish for `main`.
   - Tag-driven publish for `v*`.

## Detailed Design

### A. CI Main Gate

`CI` should include:

1. `backend-quality`
2. `frontend-quality`
3. `docker-build-check` (PR)
4. `smoke-e2e` (new)

Execution goals:

1. Median PR feedback <= 15 minutes.
2. Deterministic pass/fail semantics suitable for branch protection.

Recommended required checks (GitHub branch protection):

1. `CI / backend-quality`
2. `CI / frontend-quality`
3. `CI / smoke-e2e`
4. `CI / docker-build-check` (PR context)

### B. Smoke E2E Strategy

Only high-value, low-flake paths should block merges:

1. Teacher core chat happy path.
2. Teacher upload minimal lifecycle.
3. Student core learning/submit interaction.
4. Mobile session menu accessibility/key navigation regression.

Implementation pattern:

1. Add `npm run e2e:smoke`.
2. Use grep or dedicated smoke specs to bound runtime.
3. Keep mock-first API routing for determinism.
4. Continue uploading Playwright artifacts on failure.

Non-smoke full E2E remains available for periodic confidence but does not block most PRs.

### C. Image Publish Gating (Automatic + Safe)

`Build and Push Images` should publish automatically in two cases:

1. `workflow_run` from `CI` when:
   - conclusion is `success`
   - branch is `main`
2. `push` event on `v*` tags.

Tagging policy:

1. `main` CI-success path: `latest`, `sha-<shortsha>`.
2. Tag path (`vX.Y.Z`): `vX.Y.Z`, `sha-<shortsha>` (and optionally `latest`, configurable).

Operational hardening:

1. Add workflow `concurrency` to reduce parallel publish races.
2. Emit pushed image tags and digests in job summary for quick verification.
3. Keep lowercase repository canonicalization (`${GITHUB_REPOSITORY,,}`) to avoid package path drift.

## Security and Supply-Chain Baseline (Balanced Scope)

Not full enterprise hardening yet, but minimum recommended additions:

1. Pin critical third-party actions to immutable SHAs where practical.
2. Add container vulnerability scan on publish path (non-blocking at first, later blocking on high/critical).
3. Add SBOM generation artifact for published images.

These are phase-2 tasks and do not block the first balanced rollout.

## Rollout Plan (1 Week)

1. **Day 1**
   - Rewire `docker.yml` triggers to `CI success on main` + `v* tags`.
   - Add publish guard conditions and concurrency.

2. **Day 2**
   - Add `smoke-e2e` into primary CI.
   - Keep existing E2E workflows as supplementary checks.

3. **Day 3**
   - Introduce coverage fail-under threshold with conservative initial target.
   - Expand static checks to critical directories where runtime risk is highest.

4. **Day 4**
   - Improve diagnostics: job summaries, artifact naming consistency, and quick-failure hints.

5. **Day 5**
   - Document trigger matrix and required checks in ops docs for maintainability.

## Acceptance Criteria

1. `CI failed + image published` incidents on `main`: **0** across 20 consecutive merges.
2. PR `CI` median duration: **<= 15 minutes**.
3. Smoke E2E weekly flake rate: **< 2%**.
4. Image publish evidence includes digest traceability in workflow summary for each image.

## Risks and Mitigations

1. **Risk:** Smoke suite still flaky.
   - **Mitigation:** keep smoke test count minimal, avoid external dependencies, preserve artifact debug data.

2. **Risk:** CI runtime grows above target.
   - **Mitigation:** parallelize jobs, cache dependencies, cap smoke scope.

3. **Risk:** Developer confusion about E2E responsibilities.
   - **Mitigation:** explicitly document "blocking smoke vs non-blocking full E2E."

## Out of Scope

1. Automated deploy to staging or production.
2. Runtime rollback automation.
3. Full SLSA/cosign attestation pipeline.

These can be revisited when the project transitions from demo readiness to production operations.


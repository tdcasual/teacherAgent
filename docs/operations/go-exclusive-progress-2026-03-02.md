# Go-Exclusive Progress (2026-03-02)

## Scope

Track execution progress toward Go-exclusive runtime cutover.

## Step Status

1. Backend v2 route wiring on Go runtime: **DONE**
   - `/healthz`, `/health`
   - `/charts/{runID}/{fileName}`
   - `/chart-runs/{runID}/meta`
   - `/api/v2/auth/student/login`
   - `/api/v2/files/upload`
   - `/api/v2/assignment/confirm`
   - `/api/v2/exam/parse`
   - `/api/v2/chat/send`
   - `/api/v2/chat/events`
   - `/api/v2/jobs/{jobID}`
   - `/api/v2/admin/teacher/reset-token`
2. Go-exclusive deploy path files: **DONE**
   - `services/go-api/Dockerfile`
   - `docker-compose.go-exclusive.yml`
   - `scripts/release/smoke_go_api_v2.sh`
3. Go runtime verification: **DONE**
   - `go test ./...` passed in container.
   - `smoke_go_api_v2.sh` passed (20 cases).
4. Frontend v2-only traffic gate: **DONE**
   - Legacy student and teacher feature modules removed from active frontend apps.
   - Student and teacher app entrypoints are now hard-cut to minimal Go v2 consoles.
   - `scripts/release/check_frontend_api_v2_only.sh` now passes with zero findings.
5. End-to-end go-exclusive verification (post-frontend hard-cut): **DONE**
   - `npm run build:student` passed.
   - `npm run build:teacher` passed.
   - `API_BASE=http://localhost:18000 bash scripts/release/smoke_go_api_v2.sh` passed (20 cases).
   - `scripts/release/cutover_checklist.sh` passed.
6. Model policy hard-cut (no routing): **DONE**
   - Runtime config locked to 2 active slots: `embedding` and shared `drawing`.
   - Routing/provider-registry frontend e2e suites removed from active tree.
   - Future image/video capabilities retained as disabled extension slots.

## Current Blocker

No functional blocker identified for Go-exclusive cutover under the retained scope.

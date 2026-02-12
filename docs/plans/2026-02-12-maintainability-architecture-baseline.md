# Maintainability & Architecture Refactor Baseline (2026-02-12)

This document records the baseline before executing the 2-week maintainability and architecture refactor.

## Commands Executed

- `python3 -m pytest -q`
- `npm run typecheck` (cwd: `frontend`)
- `npm run build:student` (cwd: `frontend`)
- `wc -l services/api/app_core.py frontend/apps/student/src/App.tsx`

## Baseline Results

### Backend Tests

- Status: PASS
- Output summary: `1216 passed, 2 skipped, 1 warning in 17.03s`
- Notable warning: `NotOpenSSLWarning` from local Python `ssl`/`urllib3` environment.
- Notable runtime signal: repeated thread-related logging noise during teardown (chat worker / `CURRENT_CORE` fallback warnings).

### Frontend Type Check

- Status: PASS
- Command: `npm run typecheck`

### Frontend Student Build

- Status: PASS with size warning
- Largest emitted JS chunk: `dist-student/assets/index-Dnj5EKw2.js` at `686.08 kB` (gzip `208.04 kB`)
- Build warning: chunk > 500 kB, needs code-splitting/manual chunking.

### Maintainability Hotspot Line Counts

- `services/api/app_core.py`: `1374` lines
- `frontend/apps/student/src/App.tsx`: `1767` lines

## Baseline Targets (for end-of-plan comparison)

- Reduce `services/api/app_core.py` by at least 35%.
- Reduce `frontend/apps/student/src/App.tsx` by at least 40%.
- Reduce largest student JS chunk under 550 kB.
- Keep full pytest suite green.

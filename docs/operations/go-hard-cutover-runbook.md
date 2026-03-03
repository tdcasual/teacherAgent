# Go Hard Cutover Runbook

Date: 2026-03-02
Scope: One-shot cutover from legacy runtime to Go runtime
Window: 1-2 days maintenance

## Preconditions

1. Release artifact for `services/go-api` is built and immutable.
2. Smoke suite is ready and mapped to `20-30` required cases.
3. Rollback snapshot plan is validated.
4. `docker-compose.go-exclusive.yml` is available and validated.

## Cutover Steps

1. Announce maintenance start and freeze write traffic.
2. Stop old backend.
3. Backup old database.
4. Deploy go-api.
5. Switch frontend API target to `/api/v2`.
6. Run v2 smoke suite.
7. Verify core SLO metrics and error code rates.
8. Reopen traffic after smoke and SLO gates pass.

## Command Skeleton (Go-Exclusive)

```bash
# 1) stop old runtime
docker compose down

# 2) deploy go-api only runtime
docker compose -f docker-compose.go-exclusive.yml up -d --build api

# 3) run go-api v2 smoke
bash scripts/release/smoke_go_api_v2.sh

# 4) verify frontend has no legacy endpoint calls before final cutover
bash scripts/release/check_frontend_api_v2_only.sh
```

## Verification Gates

1. All smoke cases pass.
2. Health endpoint returns `{"status":"ok"}`.
3. Error rate remains within agreed baseline.
4. No critical job queue backlog growth.

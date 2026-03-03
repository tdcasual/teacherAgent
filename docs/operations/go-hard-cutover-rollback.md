# Go Hard Cutover Rollback Runbook

Date: 2026-03-02
Scope: Emergency rollback from current go-api release to previous stable go-api release

## Trigger Conditions

1. Smoke gate failures that block core teacher/student/admin loops.
2. Sustained critical error rate above rollback threshold.
3. Data integrity risk detected in production.

## Rollback Steps

1. Freeze traffic and announce rollback start.
2. Stop go-api.
3. Restore database snapshot.
4. Re-enable previous stable go-api release.
5. Repoint frontend API target back to previous runtime.
6. Run rollback smoke suite.
7. Confirm recovery metrics and close incident.

## Exit Criteria

1. Previous backend health endpoints are stable.
2. Core user flows pass rollback smoke checks.
3. Incident timeline and impact summary are documented.

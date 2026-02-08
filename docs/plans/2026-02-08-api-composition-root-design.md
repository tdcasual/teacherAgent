# API Composition Root (C Effect) Design

**Date:** 2026-02-08

## Goal
Make `services/api/app.py` a true composition root: only route registration, light request/response mapping, dependency wiring, and dynamic tenant wiring. Remove all inline/background workers from the API process. All async work must be executed by an RQ worker service backed by Redis.

## Summary
- **API**: synchronous HTTP edge; validates input, saves files, writes `job.json`, enqueues tasks, and serves status/draft/confirm. **No background threads or inline workers.**
- **Worker**: RQ worker(s) execute tasks (chat, exam upload parse, assignment upload parse, profile updates, etc.) and update `job.json` and outputs.
- **Redis**: mandatory broker/result store **and** lane-serialisation coordination for chat jobs.
- **Multi-tenant**: every job carries tenant_id; worker loads tenant module and restores DATA_DIR/UPLOADS_DIR/limits from sqlite store.
- **Failure mode**: API **fails fast** if Redis/RQ not configured or unreachable (no fallback).

## Architecture & Responsibilities
### API (composition root only)
- Build FastAPI app, include routers, wire dependencies.
- Request mapping: params validation, file persistence, `job.json` write, enqueue to RQ, return job_id.
- Status/draft/confirm endpoints read/write the same files and preserve existing response contracts.
- **No worker threads, no inline queueing, no in-memory lane management.**

### Worker (RQ service)
- Runs `rq_worker.py` with Redis.
- Consumes queued jobs; invokes existing service functions (upload parse, exam parse, chat processing, profile update).
- Updates `job.json` and output files. Chat jobs use Redis lane store for strict per-lane serialisation.
- Can scale horizontally (multiple replicas).

### Redis
- Mandatory for RQ and lane serialisation.
- No in-process fallback. API hard-fails if not configured or unreachable.

### Multi-tenant
- API uses `MultiTenantDispatcher` and `TenantRegistry` for `/t/{tenant_id}` routing.
- Worker loads tenant module via registry and applies per-tenant settings (DATA_DIR/UPLOADS_DIR/limits) before executing tasks.

## Component Split
- `services/api/app.py`: composition root only (routers + deps + tenant wiring + startup checks).
- `services/api/routers/*`: domain routers (exam, assignment, chat, profile, health, uploads, tenant admin).
- `services/api/*_service.py`: business logic (no HTTP).
- `services/api/queue_backend.py`: RQ-only backend (raise if not configured).
- `services/api/rq_tasks.py`: enqueue + worker task wrappers.
- `services/api/rq_worker.py`: worker entrypoint.
- `services/api/deps.py` (or similar): dependency factories (Redis clients, lane store, job stores).

## Runtime Data Flow
1. API receives request → validates → saves files → writes `job.json` with `status=queued`.
2. API enqueues task via RQ.
3. Worker consumes job → loads tenant module → executes service → updates `job.json` → produces outputs.
4. Chat jobs use Redis lane store to ensure per-lane serialisation; next job in lane is enqueued only after completion.

## Error Handling
- API startup **fails fast** when Redis/RQ missing or unreachable.
- Worker errors update `job.json` with `status=failed`, `error`, `error_detail` without changing API contracts.
- API returns 500/503 for misconfiguration or runtime errors with clear messages.

## Testing
- API startup fails without Redis/RQ configuration.
- Lifespan does not start any background workers.
- Queue backend raises when Redis/RQ missing; no inline fallback.
- Chat lane serialisation uses Redis store unconditionally.
- Worker respects `TENANT_ID` and `RQ_SCAN_PENDING_ON_START`.
- Multi-tenant dispatcher continues to route `/t/{tenant_id}` correctly.

## Migration & Rollout
1. Deploy Redis and RQ worker service first.
2. Deploy API with hard-fail checks enabled.
3. Confirm job status polling remains unchanged.
4. Rollback by reverting to prior commit if needed (no inline fallback in this design).

## Non-Goals
- Changing job file formats or response schemas.
- Reworking OCR/LLM behavior.
- Altering frontend polling contracts.

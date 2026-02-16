# Teacher Chat Streaming Optimization Design (Executed)

## Goal

Improve teacher chat streaming efficiency and UX smoothness while preserving existing SSE/fallback semantics and backward compatibility.

## Scope

- Backend event stream read efficiency for long-running streams.
- Frontend stream render efficiency for high-frequency `assistant.delta` events.
- Strengthen event protocol contract with explicit versioning and typed frontend parser.

## Baseline Issues

1. Backend `/chat/stream` repeatedly scanned full `events.jsonl` on each polling tick, even when cursor had already advanced.
2. Backend stream loop used fixed-interval sleep polling even in idle periods.
3. Frontend stream consumer updated tool state (`setPendingToolRuns`) on every `assistant.delta`, causing unnecessary re-renders and process panel churn.

## Design

### 1) Backend incremental event loading

- Add `load_chat_events_incremental(job_id, after_event_id, offset_hint, limit)` in `services/api/chat_event_stream_service.py`.
- Behavior:
  - If `offset_hint` is valid, seek directly to that byte offset and read appended lines.
  - If `offset_hint` is missing/invalid/out-of-range, fallback to full scan from file start.
  - Filter by `event_id > after_event_id` and cap by `limit`.
  - Return `(events, next_offset)` for next loop reuse.
- Route integration:
  - `services/api/routes/chat_routes.py` stream loop now keeps `log_offset` and passes it to incremental loader.

### 2) Backend event-driven wakeup (idle wait)

- Add in-memory per-job stream signal primitives in `services/api/chat_event_stream_service.py`:
  - `notify_chat_stream_event(job_id)`
  - `wait_for_chat_stream_event(job_id, last_seen_version, timeout_sec)`
- Extend `ChatEventStreamDeps` with optional callbacks:
  - `notify_job_event`
  - `wait_job_event`
- Wiring integration (`services/api/wiring/chat_wiring.py`):
  - inject notify/wait callbacks into chat event stream deps.
- Route integration (`services/api/routes/chat_routes.py`):
  - when no events, wait by callback (`asyncio.to_thread(wait_job_event, ...)`) with timeout;
  - fallback to short sleep if callback unavailable.
- Effect:
  - stream loop wakes mostly on event arrival (or timeout), reducing idle hot-loop CPU.

### 3) Frontend delta render throttling

- In `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts` stream loop:
  - Add a 40ms timer coalescing for `assistant.delta` / `assistant.done` placeholder updates.
  - Keep tool state updates immediate only for `tool.start`/`tool.finish`.
  - Clear pending render timer on terminal events/error/reconnect cleanup.

### 4) Event protocol versioning + typed parsing

- Backend (`services/api/chat_event_stream_service.py`):
  - Add `CHAT_STREAM_EVENT_VERSION = 1`.
  - Persist `event_version` in appended events.
  - Include `event_version` in SSE data envelope.
- Frontend (`frontend/apps/teacher/src/features/chat/streamEventProtocol.ts`):
  - Add shared parser `parseChatStreamEnvelope(rawData)` with runtime shape checks.
  - Normalize default version when envelope omits it.
  - Return typed envelope for stream consumer use.
- Frontend consumer integration:
  - `useTeacherChatApi.ts` now parses envelope through protocol helper instead of ad-hoc JSON cast.

## Compatibility

- SSE transport format remains `id/event/data`; payload adds backward-compatible `event_version`.
- `last_event_id` resume semantics unchanged.
- Polling fallback behavior unchanged.
- Teacher process panel behavior unchanged except reduced redundant repainting.

## Tests Added/Updated

- Backend:
  - `tests/test_chat_event_stream_service.py`
    - incremental loader reuses offset
    - incremental loader fallback on invalid offset hint
    - notify/wait signal version semantics
  - Existing stream route tests still pass.
  - `tests/test_chat_stream_route.py`
    - new case: stream route uses wait callback during idle no-event state.
- Frontend:
  - `frontend/apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx`
    - new test ensures delta-only streams do not spam tool-state updates.
  - `frontend/apps/teacher/src/features/chat/streamEventProtocol.test.ts`
    - parser accepts valid envelope, rejects invalid shape, and preserves explicit version.

## Verification Results

- `python3 -m pytest -q tests/test_chat*.py` -> `307 passed`
- `cd frontend && npx vitest run apps/teacher/src/features/chat/ChatMessages.test.tsx apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx apps/teacher/src/features/chat/streamEventProtocol.test.ts` -> `10 passed`
- `cd frontend && npm run -s typecheck` -> pass
- Full regression:
  - `python3 -m pytest -q` -> `1954 passed, 2 skipped`
  - `cd frontend && npx vitest run` -> `50 passed`

## Next Optional Optimizations

1. Introduce event-log retention/compaction policy for very long-lived job artifacts.
2. Add coarse performance telemetry (idle wakeups, events/sec, stream reconnect rate) for capacity planning.
3. Optionally add protocol migration guardrails for future `event_version > 1` envelopes.

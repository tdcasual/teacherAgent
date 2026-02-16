# Teacher Chat Streaming Design (SSE + Event Log)

## Goal
- Keep existing `/chat/start` + `/chat/status` compatibility.
- Add teacher-side streaming that reflects runtime progress similar to Codex:
  - queue/processing state
  - tool start/finish events
  - assistant incremental text updates
- Support reconnect/resume after refresh/network jitter.

## Protocol
- New endpoint: `GET /chat/stream?job_id=...&last_event_id=...`
- Content type: `text/event-stream`
- Event envelope:
  - `id`: monotonic event id
  - `event`: event type
  - `data`: JSON object `{ event_id, type, payload }`
- First response frame includes `retry: 1000`.

## Event Storage
- Per job file: `chat_jobs/<job_id>/events.jsonl`
- Sequence sidecar: `chat_jobs/<job_id>/events.seq`
- New server module:
  - append event with monotonic id under chat lock
  - read events after `last_event_id`
  - encode SSE frame

## Event Types (v1)
- `job.queued`
- `job.processing`
- `llm.round.start`
- `tool.start`
- `tool.finish`
- `assistant.delta`
- `assistant.done`
- `job.done`
- `job.failed`
- `job.cancelled`

## Backend Integration
- `chat_start_service` appends `job.queued`.
- `chat_job_processing_service`:
  - status transitions append `job.processing/job.done/job.failed/job.cancelled`
  - runtime event sink appends tool and assistant events
  - fallback emits assistant events when runtime did not stream reply.
- `agent_service` tool loop emits:
  - per-round markers
  - per-tool start/finish
  - assistant delta/done for final reply.

## Frontend Integration (Teacher)
- `useTeacherChatApi` changed from polling-first to:
  1. open SSE stream
  2. parse and apply events incrementally
  3. auto reconnect with `last_event_id`
  4. fallback to legacy polling after repeated stream failures.
- UI behavior:
  - queue hint remains live
  - placeholder assistant bubble shows tool timeline + incremental text
  - final turn content is cleaned to final assistant reply only.

## Rollout
- No breaking change to existing status polling path.
- Stream failures degrade gracefully to current behavior.
- Scope is teacher-side chat only.

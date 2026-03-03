# HTTP API v2 Contract (Hard-Cut Rewrite)

Status: Draft for Go hard-cut migration
Date: 2026-03-02

## Response Conventions

Successful responses return domain payloads with HTTP `2xx`.

Error responses share one envelope:

```json
{
  "error_code": "AUTH_INVALID_CREDENTIAL",
  "message": "invalid credential"
}
```

## Core Endpoints (Current Draft)

### Health

- `GET /healthz`
- Response:

```json
{
  "status": "ok"
}
```

### Auth

- `POST /api/v2/auth/student/login`
- Request:

```json
{
  "student_id": "stu-1",
  "credential": "S-123"
}
```

- Response:

```json
{
  "access_token": "..."
}
```

### Files

- `POST /api/v2/files/upload`
- Request:

```json
{
  "file_name": "lesson.pdf",
  "size_bytes": 1024
}
```

- Response:

```json
{
  "resource_id": "res-1"
}
```

### Assignment

- `POST /api/v2/assignment/confirm`
- Request:

```json
{
  "draft_id": "draft-1"
}
```

- Response:

```json
{
  "status": "queued"
}
```

### Exam

- `POST /api/v2/exam/parse`
- Request:

```json
{
  "resource_id": "res-1"
}
```

- Response:

```json
{
  "job_id": "job-1",
  "status": "queued"
}
```

### Chat

- `POST /api/v2/chat/send`
- Request:

```json
{
  "session_id": "s-1",
  "message": "hello"
}
```

- Response:

```json
{
  "job_id": "chat-job-1",
  "status": "queued"
}
```

- `GET /api/v2/chat/events?job_id=<id>`
- Response content type: `text/event-stream`

### Jobs

- `GET /api/v2/jobs/{job_id}`
- Response:

```json
{
  "job_id": "chat-job-1",
  "state": "done"
}
```

### Admin

- `POST /api/v2/admin/teacher/reset-token`
- Request:

```json
{
  "teacher_id": "t-1"
}
```

- Response:

```json
{
  "token": "T-NEW-1"
}
```

### Chart Assets

- `GET /charts/{run_id}/{file_name}`
- Response: chart binary file stream

- `GET /chart-runs/{run_id}/meta`
- Response:

```json
{
  "ok": true,
  "points": 3
}
```

## Notes

- v1 compatibility endpoints are intentionally excluded.
- This contract is updated incrementally as new Go endpoints land.

# MCP Interface

This document describes the MCP sidecar interface. The product surface is **student + bound assignment.list/render only**.

`lesson.*` and `core_example.*` are **not** MCP tools. HTTP and teacher-chat physics affiliates are unchanged.

## Endpoint
- **URL**: `/mcp`
- **Protocol**: JSON-RPC 2.0
- **Auth**: required. Send `X-API-Key: <MCP_API_KEY>`.
- Empty or missing `MCP_API_KEY` configuration makes `POST /mcp` return `503` with `mcp_auth_not_configured`.
- Missing or wrong `X-API-Key` returns `401`.

## Health Check
- `GET /health` → `{ "status": "ok" }`
- Unauthenticated **only** because compose publishes MCP on loopback (`127.0.0.1:9000`).

## Runtime
- `MCP_SCRIPT_TIMEOUT_SEC` (optional): script timeout (seconds). Default `600`. Set `0/none/inf` for no timeout.
- `MCP_BOUND_TEACHER_ID` (optional): when set, `tools/list` also includes mutating student/assignment tools and `assignment.list` / `assignment.render` are scoped to that teacher.
- This wave reads assignment `meta.json` and `data/student_profiles/*.json` from disk. MCP does not SQL-gate these tools.
- Script allowlist is explicit:
  - `skills/physics-student-coach/scripts/update_profile.py`
  - `scripts/render_assignment_pdf.py`

### Tool table

| Tool | Unbound (`MCP_BOUND_TEACHER_ID` empty) | Bound |
| --- | --- | --- |
| `student.search` | listed + callable | listed + callable |
| `student.profile.get` | listed + callable | listed + callable |
| `student.profile.update` | not listed; `tools/call` → JSON-RPC `403` `mcp_teacher_unbound` | listed + callable |
| `assignment.list` | not listed; `tools/call` → result `{"error":"mcp_teacher_unbound"}` | listed; folders whose `meta.json` `teacher_id` equals the bound teacher |
| `assignment.render` | not listed; `tools/call` → JSON-RPC `403` `mcp_teacher_unbound` | listed; owner mismatch → JSON-RPC `403` `forbidden_assignment_owner` |

---

## JSON-RPC Methods

### 0) initialize (optional)
Return server info and capabilities.

**Request**
```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "method": "initialize",
  "params": {}
}
```

### 1) tools/list
Return the list of available tools for the current bind state.

**Request**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [
    {
      "name": "student.profile.get",
      "description": "Get student profile JSON",
      "inputSchema": { "...": "JSON Schema for tool arguments" }
    }
  ]
}
```

---

### 2) tools/call
Invoke a tool.

**Request**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "student.profile.get",
    "arguments": {
      "student_id": "高二2403班_武熙语"
    }
  }
}
```

---

## Tool Definitions

### student.search
**Purpose**: Search students by name/keyword (from `data/student_profiles/*.json`).

**Arguments**
- `query` (string, required)
- `limit` (integer, optional)

**Result**
- `{ ok, query, students: [{ student_id, student_name, class_name }] }`

### student.profile.get
**Purpose**: Load student profile JSON.

**Arguments**
- `student_id` (string, required)

**Result**
- JSON from `data/student_profiles/<student_id>.json`

---

### student.profile.update
**Purpose**: Update derived student profile fields. Mutating; listed only when `MCP_BOUND_TEACHER_ID` is set.

**Arguments**
- `student_id` (string, required)
- `weak_kp` (string, optional, comma-separated)
- `strong_kp` (string, optional)
- `medium_kp` (string, optional)
- `next_focus` (string, optional)
- `interaction_note` (string, optional)

**Result**
- stdout from `update_profile.py`

**Unbound**
- JSON-RPC error `{ "code": 403, "message": "mcp_teacher_unbound" }`

---

### assignment.list
**Purpose**: List assignment folder names under `data/assignments/` whose `meta.json` `teacher_id` equals `MCP_BOUND_TEACHER_ID`.

**Arguments**: none

**Result**
- `{ ok, assignments: ["A2403_2026-02-04", ...] }` filtered to the bound teacher

**Unbound**
- result `{ "error": "mcp_teacher_unbound" }` (JSON-RPC success envelope)

---

### assignment.render
**Purpose**: Render assignment PDF (requires `reportlab`). Mutating; listed only when `MCP_BOUND_TEACHER_ID` is set.

**Arguments**
- `assignment_id` (string, required)
- `assignment_questions` (string path, optional; default `data/assignments/<id>/questions.csv`)
- `out` (string path, optional)

**Result**
- stdout from `render_assignment_pdf.py`

**Unbound**
- JSON-RPC error `{ "code": 403, "message": "mcp_teacher_unbound" }`

**Owner mismatch**
- JSON-RPC error `{ "code": 403, "message": "forbidden_assignment_owner" }`

---

## Removed from MCP

These names are not registered and `tools/call` returns unknown tool. HTTP / teacher-chat surfaces are unchanged.

- `lesson.*` — lesson capture remains an HTTP/chat physics affiliate, not MCP.
- `core_example.*` — core-example register/search/render remain HTTP/chat affiliates, not MCP.
- `exam.*` — not an MCP tool.
- `assignment.generate` — generate via HTTP `POST /assignment/generate` or teacher chat.

---

## Notes
- All file paths passed to MCP must resolve under `DATA_DIR` or `UPLOADS_DIR` (symlink escape is rejected).
- MCP only writes derived fields; no raw scores are stored.
- Auth is required on `/mcp`. Set a strong `MCP_API_KEY`; an empty key fails closed (`503`) and compose will not start without one.

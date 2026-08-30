# MCP Interface

This document describes the MCP server interface exposed by this project.

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
- `MCP_BOUND_TEACHER_ID` (optional): when set, registers mutating assignment/student/lesson/core_example tools and filters `assignment.list` / `assignment.render` to that teacher. When empty, those tools are unregistered.
- `exam.*` and `assignment.generate` are not MCP tools. Generate assignments via HTTP or teacher chat. Exam HTTP/MCP surfaces have been removed.

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
Return the list of available tools.

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
**Purpose**: Update derived student profile fields.

**Arguments**
- `student_id` (string, required)
- `weak_kp` (string, optional, comma-separated)
- `strong_kp` (string, optional)
- `medium_kp` (string, optional)
- `next_focus` (string, optional)
- `interaction_note` (string, optional)

**Result**
- stdout from `update_profile.py`

---

### assignment.list
**Purpose**: List assignments owned by `MCP_BOUND_TEACHER_ID`. Unregistered when that env var is empty.

**Arguments**: none (`teacher_id` in args is ignored)

**Result**
- `{ ok, assignments: ["A2403_2026-02-04", ...] }` filtered to the bound teacher

---

### lesson.capture
**Purpose**: OCR and extract lesson materials.

**Arguments**
- `lesson_id` (string, required)
- `topic` (string, required)
- `sources` (array, required; list of file paths)
- `discussion_notes` (string path, optional)
- `lesson_plan` (string path, optional)
- `force_ocr` (boolean, optional)
- `ocr_mode` (string, optional)
- `language` (string, optional)
- `out_base` (string, optional)

**Result**
- stdout from `lesson_capture.py`

---

### core_example.search
**Purpose**: Query core examples.

**Arguments**
- `kp_id` (string, optional)
- `example_id` (string, optional)

**Result**
- Rows from `data/core_examples/examples.csv`

---

### core_example.register
**Purpose**: Register a core example (writes to `data/core_examples/` + appends `examples.csv`). Mutating; registered only when `MCP_BOUND_TEACHER_ID` is set.

**Arguments**
- `example_id` (string, required)
- `kp_id` (string, required)
- `core_model` (string, required)
- plus optional fields matching `register_core_example.py` flags

**Result**
- stdout from `register_core_example.py`

---

### core_example.render
**Purpose**: Render a core example into PDF.

**Arguments**
- `example_id` (string, required)
- `out` (string path, optional)

**Result**
- stdout from `render_core_example_pdf.py`

---

### assignment.generate
**Purpose**: Not an MCP tool. Generate via HTTP `POST /assignment/generate` or teacher chat `assignment.generate` (writes draft). MCP no longer registers this name.

**Arguments**
- `assignment_id` (string, required)
- `kp` (string, optional; required if no `question_ids`)
- `question_ids` (string, optional; required if no `kp`)
- `core_examples` (string, optional)
- `generate` (boolean, optional)

**Result**
- stdout from `select_practice.py`

---

### assignment.render
**Purpose**: Render assignment PDF (requires `reportlab`).

**Arguments**
- `assignment_id` (string, required)
- `assignment_questions` (string path, optional; default `data/assignments/<id>/questions.csv`)
- `out` (string path, optional)

**Result**
- stdout from `render_assignment_pdf.py`

---

## Notes
- All file paths passed to MCP must resolve under `DATA_DIR` or `UPLOADS_DIR` (symlink escape is rejected).
- MCP only writes derived fields; no raw scores are stored.
- Auth is required on `/mcp`. Set a strong `MCP_API_KEY`; an empty key fails closed (`503`) and compose will not start without one.

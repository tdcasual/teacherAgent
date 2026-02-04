# MCP Interface (Physics Agent)

This document describes the MCP server interface exposed by this project.

## Endpoint
- **URL**: `/mcp`
- **Protocol**: JSON-RPC 2.0
- **Auth**: `X-API-Key: <MCP_API_KEY>` (if configured)

## Health Check
- `GET /health` → `{ "status": "ok" }`

---

## JSON-RPC Methods

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
    {"name": "student.profile.get", "description": "Get student profile"},
    {"name": "student.profile.update", "description": "Update student profile (derived)"},
    {"name": "lesson.capture", "description": "Capture lesson materials (OCR + examples)"},
    {"name": "core_example.search", "description": "Search core examples"},
    {"name": "assignment.generate", "description": "Generate assignment from KP or core examples"}
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

### lesson.capture
**Purpose**: OCR and extract lesson materials.

**Arguments**
- `lesson_id` (string, required)
- `topic` (string, required)
- `sources` (array, optional; list of file paths)
- `discussion_notes` (string path, optional)

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

### assignment.generate
**Purpose**: Generate assignment from KP or core example templates.

**Arguments**
- `assignment_id` (string, required)
- `kp` (string, required)
- `core_examples` (string, optional)
- `generate` (boolean, optional)

**Result**
- stdout from `select_practice.py`

---

## Notes
- All file paths passed to MCP should exist inside the container volume.
- MCP only writes derived fields; no raw scores are stored.
- For production, restrict MCP with a strong `MCP_API_KEY`.

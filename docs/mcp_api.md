# MCP Interface (Physics Agent)

This document describes the MCP server interface exposed by this project.

## Endpoint
- **URL**: `/mcp`
- **Protocol**: JSON-RPC 2.0
- **Auth**: `X-API-Key: <MCP_API_KEY>` (if configured)

## Health Check
- `GET /health` → `{ "status": "ok" }`

## Runtime
- `MCP_SCRIPT_TIMEOUT_SEC` (optional): script timeout (seconds). Default `600`. Set `0/none/inf` for no timeout.

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
      "name": "exam.analysis.get",
      "description": "Get exam analysis draft (or compute minimal totals)",
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

### exam.list
**Purpose**: List available exams (from `data/exams/*/manifest.json`).

**Arguments**: none

**Result**
- `{ ok, exams: [{ exam_id, generated_at, students, responses }] }`

---

### exam.get
**Purpose**: Get exam manifest + totals summary.

**Arguments**
- `exam_id` (string, required)

**Result**
- `{ ok, exam_id, generated_at, counts, totals_summary, files, ... }`

---

### exam.analysis.get
**Purpose**: Get precomputed analysis draft; fallback to minimal totals if missing.

**Arguments**
- `exam_id` (string, required)

**Result**
- `{ ok, exam_id, analysis, source }`

---

### exam.students.list
**Purpose**: List students in exam with total score + rank.

**Arguments**
- `exam_id` (string, required)
- `limit` (integer, optional)

**Result**
- `{ ok, exam_id, total_students, students: [...] }`

---

### exam.student.get
**Purpose**: Get one student's per-question breakdown within an exam.

**Arguments**
- `exam_id` (string, required)
- `student_id` (string, optional)
- `student_name` (string, optional)
- `class_name` (string, optional)

**Result**
- `{ ok, exam_id, student, question_scores }`

---

### exam.question.get
**Purpose**: Get one question's score distribution within an exam.

**Arguments**
- `exam_id` (string, required)
- `question_id` (string, optional)
- `question_no` (string, optional)

**Result**
- `{ ok, exam_id, question, stats, distribution, top_students, bottom_students }`

---

### assignment.list
**Purpose**: List assignments (folder names under `data/assignments/`).

**Arguments**: none

**Result**
- `{ ok, assignments: ["A2403_2026-02-04", ...] }`

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
**Purpose**: Register a core example (writes to `data/core_examples/` + appends `examples.csv`).

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
**Purpose**: Generate assignment from KP or core example templates.

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
- All file paths passed to MCP should exist inside the container volume.
- MCP only writes derived fields; no raw scores are stored.
- For production, restrict MCP with a strong `MCP_API_KEY`.

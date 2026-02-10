# Student Profile Schema (Derived)

This profile is derived from exam responses, practice history, and chat interactions.
It is safe to update after student interactions. Only derived fields may be modified.

## Schema

| Field | Type | Updated By | Description |
|-------|------|-----------|-------------|
| `student_id` | string (required) | import/create | Unique identifier |
| `student_name` | string | import | Student display name |
| `class_name` | string | import | Class name |
| `created_at` | ISO timestamp | create | Profile creation time |
| `last_updated` | ISO timestamp | every update | Last modification time |
| `aliases` | string[] | import | Name variations |
| `recent_weak_kp` | string[] | Layer 1 + Layer 2 | Top 3-5 weak knowledge points |
| `recent_strong_kp` | string[] | Layer 1 + Layer 2 | Strong knowledge points |
| `recent_medium_kp` | string[] | Layer 1 + Layer 2 | Medium mastery points |
| `next_focus` | string | Layer 1 + Layer 2 | What to work on next |
| `misconceptions` | object[] | Layer 1 + Layer 2 | Typical error patterns |
| `mastery_by_kp` | object | Layer 2 only | Per-KP accuracy and attempts |
| `interaction_notes` | object[] | Layer 1 + Layer 2 | Last 20 structured notes |
| `practice_history` | object[] | assignment flow | Last 20 assignment records |
| `summary` | string | Layer 2 | Readable paragraph for teacher |
| `import_history` | object[] | import | Last 10 import records |

## Field Details

### misconceptions
```json
[{"description": "混淆了速度和加速度", "detected_at": "2026-02-10T10:00:00"}]
```

### mastery_by_kp
```json
{"KP-ID": {"accuracy": 0.7, "attempts": 3, "last_updated": "2026-02-10T10:00:00"}}
```

### interaction_notes
```json
[{"timestamp": "ISO", "note": "[话题] 牛顿 | [学生] 答对 | [诊断] 掌握:牛顿", "source": "rule"}]
```
- `source`: `rule` (Layer 1 real-time) or `llm` (Layer 2 session summary)

### practice_history
```json
[{"assignment_id": "", "timestamp": "ISO", "status": "completed", "matched": 5, "graded": 4, "ungraded": 1}]
```
- `status`: `completed` | `partial` | `abandoned`

## Rules

- Do NOT change raw exam scores or responses.
- Only update derived fields.
- Keep interaction_notes concise and structured (max 200 chars per note).
- Keep a readable summary for teacher review.
- Sensitive data must remain masked (ScoreBand/RankBand) in mem0.

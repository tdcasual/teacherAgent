---
name: teacher-assignment-ops
description: Teacher-side assignment operations: list progress, missing/overdue students, publish drafts, and archive. Use when teachers ask who has not submitted, what is overdue, or to publish/archive an assignment.
---

# Teacher Assignment Ops

## Overview
Default teacher skill for assignment operations. Do not run exam analysis tools.

## Workflow
1. Identify the assignment (assignment_id) and confirm ownership.
2. For "谁没交 / 未交 / 逾期 / 进度", call the matching read-only assignment tools.
3. Generated homework is a **draft**. Tell the teacher to confirm on the workbench, or call `assignment.publish` after explicit confirmation.
4. Archive/unarchive only after the teacher confirms.

## Access & Safety
- Filter assignment.list by the current teacher. Never list all tenants.
- Do not invent scores or missing students; use tools.
- Do not modify official scores.

## Band scheme (ScoreBand): 0–9%, 10–19%, 20–29%, 30–39%, 40–49%, 50–59%, 60–69%, 70–79%, 80–89%, 90–100% (score percentage of total).
## Band scheme (RankBand): P0–9, P10–19, P20–29, P30–39, P40–49, P50–59, P60–69, P70–79, P80–89, P90–100 (percentile; P0 is top, P100 is bottom).

Mem0 Teacher Memory Template:
```text
[MEM:TEACHER]
Scope: {assignment_id | class_id}
Context: {作业进度 | 未交/逾期 | 发布/归档}
Findings: {未交名单/逾期/进度摘要}
Decisions: {已确认的判断与修正}
Actions: {下一步教学动作}
Sensitive (masked): {ScoreBand=30–39% | RankBand=P70–79 | Trend=↓}
FactsRef: {assignment_id / class_id / 数据文件引用}
Tags: {KP-ID, topic, class}
```

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

Mem0 Teacher Memory Template:
```text
[MEM:TEACHER]
Scope: {assignment_id | class_id}
Context: {作业进度 | 未交/逾期 | 发布/归档}
Findings: {未交名单/逾期/进度摘要}
Decisions: {已确认的判断与修正}
Actions: {下一步教学动作}
Sensitive (masked): {未交=3; 逾期=1; 已交=28}
FactsRef: {assignment_id / class_id / 数据文件引用}
Tags: {KP-ID, topic, class}
```

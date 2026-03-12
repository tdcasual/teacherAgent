# Memory Governance

本项目对 memory 采用 provenance-first 策略：先记录来源，再允许人工确认，最后才进入长期记忆。

## Three Layers

1. 实时事实（tool / data）
- 来源：考试数据、附件 OCR、assignment progress、tool 返回值。
- 特性：时效性强、可能不稳定、不应直接视为长期记忆。

2. 会话上下文（session context / session summary）
- 来源：当前对话 turn、近期会话压缩摘要。
- 特性：帮助当前回复与 workflow 编排，但默认不是长期真值。

3. 持久化 memory proposal
- 来源：manual、auto_intent、auto_infer、auto_flush、auto_student_infer、auto_assignment_evidence。
- 特性：必须保留 provenance、status、review/apply 轨迹。

## Default Safety Policy

- teacher memory：默认只自动提案，不自动应用。
- student memory：默认只自动提案，不自动应用。
- 若需要自动应用，必须显式打开配置开关，并保留 review / apply 轨迹。

## Provenance Contract

每条 proposal 至少应回答：
- 它属于哪一层：`layer`
- 它来自哪里：`source`
- 上游来源是什么：`origin` / `upstream`
- 是否已确认：`status`、`reviewed_at`、`reviewed_by`
- 是否已应用：`applied_at`、`applied_to`

## Service Boundaries

- `teacher_memory_auto_service.py`：只负责自动提案与 flush 触发。
- `teacher_memory_governance_service.py`：负责 duplicate / quota / conflict / supersede 规则。
- `teacher_memory_storage_service.py`：负责 proposal 路径、列表、删除与 applied markdown 清理。
- `teacher_memory_deps.py`：默认 wiring 真相层；优先直接装配 `teacher_memory_*_service.py`、`teacher_context_service.py`、`teacher_session_compaction_helpers.py` 与 `mem0_adapter.py` 的实现，不再回拉 `teacher_memory_core.py` 私有 helper。
- `teacher_memory_core.py`：显式兼容 façade，只导出公开 teacher memory 入口；不再承担隐式 helper 聚合层或默认 wiring 真相源。

## Storage Guidance

- 保留教学上长期有价值的偏好、稳定误区、长期目标、有效干预。
- 不把原始成绩表、逐题 OCR 噪声、短时状态抖动直接写入长期记忆。
- 对 auto_flush 这类摘要型 proposal，优先写提案，不直接落最终记忆。

## Non-memory Operational Logs

- `data/analysis/review_feedback.jsonl` 用于沉淀人工 review 处理结果，服务对象是质量运营与策略调优，不是老师/学生长期记忆。
- `data/analysis/metrics_snapshot.json` 与 `/teacher/analysis/ops` 提供的是运行时观测与运维摘要，不应被 `auto_flush` 或 memory apply 流程误当作长期事实。
- replay compare 候选与 lineage 元数据属于审计/回归资产，允许离线导出，但不进入 teacher / student memory proposal 生命周期。
- memory 服务只治理 proposal、apply 与 provenance；ops telemetry 的保留、归档与清理由 analysis 运营链路负责。

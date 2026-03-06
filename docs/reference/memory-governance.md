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

## Storage Guidance

- 保留教学上长期有价值的偏好、稳定误区、长期目标、有效干预。
- 不把原始成绩表、逐题 OCR 噪声、短时状态抖动直接写入长期记忆。
- 对 auto_flush 这类摘要型 proposal，优先写提案，不直接落最终记忆。

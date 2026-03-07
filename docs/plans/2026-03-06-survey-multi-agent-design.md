# 问卷报告分析多 Agent 架构设计

Date: 2026-03-06

## 背景

当前项目已经形成清晰的教学 workflow 主链：`role -> workflow(skill) -> prompt stack -> tool policy -> chat job -> memory side effects -> history persistence`。这条主链的价值不只是兼容现有实现，更重要的是它已经承担了产品契约、权限边界、执行状态、可解释性与历史持久化的控制平面职责。

接下来项目希望引入多 Agent 能力，并优先支持“问卷系统自动推送结果后生成班级洞察与教学建议”。同时，后续还会逐步扩展到学生分层、风险识别、自动生成后续动作，以及更多样的作业形式，例如短视频作业、非结构化报告导入等。

因此，本设计的目标不是把系统升级为开放式多 Agent 平台，而是在保留当前产品边界的前提下，引入一套可控、可扩展、可评测的 specialist-agent 编排机制。

## 设计结论

### 选型结论

- 采用“方案 2”：`Coordinator + Evidence Pipeline + Specialist Agents + Strategy Layer`
- `Coordinator` 既负责调度，也可以在简单场景直接回答
- 子 Agent 默认不直接拥有前台会话，只通过结构化 handoff contract 与 `Coordinator` 协作
- 新的输入形式优先扩展 `adapter + artifact schema`
- 新的作业方式优先扩展 `strategy`
- 只有当认知职责明显不同的时候，才新增新的 specialist agent

### 为什么保留当前主链

保留当前主链的主要原因不是兼容性，而是因为它已经定义了系统最关键的控制平面：谁拥有会话、谁能调用什么工具、谁负责写入记忆、谁对最终输出负责、一次任务如何进入状态机并被回放。多 Agent 只应该改变 workflow 的内部执行方式，而不应该推翻这条产品主链。

因此，后续的推荐链路是：

`role -> workflow -> delegation/handoff -> specialist agents -> tool policy -> chat job -> memory side effects -> history persistence`

## 范围

### V1 范围

V1 只解决一个高价值场景：问卷系统在新结果产生后，自动触发分析，并面向老师生成“班级问卷洞察 + 可执行教学建议”。

V1 输入同时支持：

- 结构化问卷数据
- PDF 报告
- 截图
- 网页导出

V1 输出重点：

- 班级层面的高信号洞察
- 教学建议
- 证据置信度与缺失说明

### 明确不做

V1 不直接做以下能力：

- 学生级名单与画像更新
- 自动生成后续动作（作业、班会话术、追访问卷）
- 直接把结论写入长期 memory 真值
- 构建开放式多 Agent 自由对话平台

这些能力放在后续 V2/V3 演进中完成。

## 总体架构

### 核心组件

1. `Survey Webhook Intake`
   - 接收问卷系统 webhook
   - 验签、幂等、归属校验、原始载荷落盘

2. `Evidence Pipeline`
   - 统一处理结构化输入与非结构化报告
   - 输出标准化 `survey_evidence_bundle`

3. `Coordinator Agent`
   - 唯一默认前台 Agent
   - 负责判断是否直接回答或委派给 specialist agent
   - 负责最终合成老师可读结果

4. `Survey Analyst Agent`
   - 第一批 specialist agent
   - 只负责 V1 的班级洞察与教学建议

5. `Agent Registry`
   - 管理 specialist agent 的注册、输入输出契约、接管条件、预算与评测

6. `Report Delivery Layer`
   - 把结构化分析产物渲染为老师可读报告
   - 负责通知、展示与后续接入教师会话

## Coordinator 设计

### 角色定位

`Coordinator` 不是纯调度器，而是“前台主 Agent + 编排器”。它是唯一默认面向用户的会话拥有者，并拥有最终输出责任。

### 两条执行路径

1. `Direct Answer Path`
   - 对于简单问题、上下文已足够的任务，`Coordinator` 直接回答

2. `Delegation Path`
   - 当任务需要专门证据处理、复杂澄清、多阶段执行或高专门化分析时，委派给 specialist agent

### 设计原则

- 用户会话不在 specialist agent 之间来回切换
- 子 Agent 返回结构化产物，不直接输出最终老师可见文本
- `Coordinator` 拥有接管、回收、兜底与最终合成权
- 后续需要“受控前台接管”的场景，可以增加显式 `takeover policy`，但仍然由 `Coordinator` 发起与回收

## Evidence Pipeline

### Intake Job

问卷结果进入系统后，第一站不是 Agent，而是 `Survey Intake Job`。这一层只做工程职责：

- webhook 验签
- 幂等键校验
- 租户 / 教师 / 班级归属识别
- 原始 payload 与附件登记
- 下载失败重试
- 标准错误码写入

### Normalization Pipeline

该层负责把不同输入形式统一成一个可供 Agent 消费的中间对象：`survey_evidence_bundle`。

结构化输入：

- 题目与选项
- 样本量与完成率
- 分组统计
- 文本回答

非结构化输入：

- PDF 表格抽取
- 截图 OCR
- 网页导出解析
- 附件文本与表格识别

### survey_evidence_bundle 建议字段

- `survey_meta`
- `audience_scope`
- `question_summaries`
- `group_breakdowns`
- `free_text_signals`
- `attachments`
- `parse_confidence`
- `missing_fields`
- `provenance`

Bundle 设计必须以结构化字段为主，而不是简单拼接给模型的一大段文本。所有 specialist agent 后续都只消费 bundle，不直接依赖 webhook 原文或原始文件。

## Handoff Contract

为了让 specialist agent 可扩展，`Coordinator` 与各 Agent 的交接协议必须显式化，而不是内部随意传 dict。

建议 handoff contract 至少包含：

- `handoff_id`
- `from_agent`
- `to_agent`
- `task_kind`
- `artifact_refs`
- `goal`
- `constraints`
- `budget`
- `return_schema`
- `status`

对问卷分析场景，`Coordinator -> Survey Analyst Agent` 的 handoff 还建议显式带上：

- `teacher_context`
- `report_mode`
- `class_scope`
- `analysis_depth`

这样以后新增 `Risk Agent`、`Action Planner`、`Video Submission Agent` 时，可以复用同一套 contract，而不是重写 Agent 间协作逻辑。

## Survey Analyst Agent

### 定位

`Survey Analyst Agent` 是一个受控分析器，不是自由发挥的通用对话体。它的输入固定为：

- `survey_evidence_bundle`
- `teacher_context`
- `task_goal`

输出固定为 `analysis_artifact`。

### V1 职责

V1 只做三件事：

1. 提炼班级层面的高信号洞察
2. 输出可执行教学建议
3. 标注证据置信度与信息缺口

### 建议输出结构

- `executive_summary`
- `key_signals`
- `group_differences`
- `teaching_recommendations`
- `confidence_and_gaps`

### V1 不负责

- 学生级名单输出
- 自动动作生成
- memory 直接写入
- 自由多轮用户对话

这保证 V1 先把“稳定分析能力”做扎实，而不是一开始把分层、行动生成、画像更新全部搅在一起。

## Agent Registry

为了方便未来新增 specialist agent，引入受控 `Agent Registry`。

### 每个 Agent 建议声明的字段

- `agent_id`
- `display_name`
- `roles`
- `accepted_artifacts`
- `task_kinds`
- `direct_answer_capable`
- `takeover_policy`
- `tool_allowlist`
- `budgets`
- `memory_policy`
- `output_schema`
- `evaluation_suite`

### 扩展原则

- 新输入形式优先扩 `adapter + artifact schema`
- 新作业形式优先扩 `strategy`
- 新认知职责才新增 `agent`

示例：

- “问卷作业”“分层作业”“错题回炉作业”大概率共用 `Assignment Planner Agent`
- “问卷统计分析”与“短视频行为观察”属于不同认知类型，更适合拆成不同 specialist agent

## 生命周期与状态机

### 会话执行状态

对于一次前台执行，建议引入以下状态：

`received -> classified -> direct_answer | handoff_preparing -> specialist_running -> specialist_returned -> synthesized -> done|failed`

### 问卷分析后台状态

对自动触发的问卷任务，再增加 artifact/job 状态：

`webhook_received -> intake_validated -> normalized -> bundle_ready -> analysis_running -> analysis_ready -> teacher_notified`

### 设计原则

- handoff 是显式状态，而不是内部隐式函数调用
- specialist 返回后必须进入 `synthesized`
- 只有 `Coordinator` 可以决定是否把结果真正交付给老师
- 任何 specialist 失败都必须可回退到 `Coordinator fallback synthesis`

## 故障处理与回退策略

### 失败分层

建议把失败分成四层：

1. `接入失败`
   - webhook 验签失败、归属不明、重复推送、附件下载失败

2. `规范化失败`
   - PDF / OCR / 网页解析不稳定、字段缺失、表格抽取不完整

3. `分析失败`
   - specialist 超时、预算耗尽、输出 schema 不合法、结论置信度过低

4. `交付失败`
   - 报告写回失败、通知失败、后续动作创建失败

### 回退原则

- `接入失败` 直接结束在工程层，不进入 Agent
- `规范化失败` 尽量产出 `partial bundle`
- `分析失败` 回到 `Coordinator fallback synthesis`
- `交付失败` 与分析本身解耦，不影响分析 artifact 的保存

### review queue

当 `bundle_confidence` 或 `analysis_confidence` 低于阈值时，自动进入 `review queue`，供后续人工确认或补充处理。该机制是未来接入短视频、复杂网页导出等不稳定输入形式时的关键稳定器。

## 测试与灰度演进

### 测试分层

1. `contract tests`
   - 验证 `Webhook -> Intake -> Bundle -> Handoff -> Analysis Artifact` 契约稳定

2. `artifact tests`
   - 建立 bundle 金标准样本，覆盖结构化输入、PDF、截图 OCR、字段缺失、混合输入

3. `agent evals`
   - 对 `Survey Analyst Agent` 建固定评测集，评估：洞察准确性、建议可执行性、证据引用率、过度推断率、缺失信息识别率

4. `workflow replay`
   - 回放真实 webhook 任务，验证状态流、事件、fallback 与最终报告一致性

### 发布阶段

建议三阶段发布：

1. `shadow mode`
   - 后台生成分析结果，不触达老师

2. `internal beta`
   - 少量教师可见，用于收集反馈

3. `default on`
   - 评测与稳定性达标后全量启用

## 后续演进路线

### V2

在复用同一 `survey_evidence_bundle` 与 `analysis_artifact` 的基础上，增加：

- `Risk / Segmentation Agent`
- 学生分层与风险识别
- 个体名单或群组建议

### V3

在同一分析产物基础上增加：

- `Action Planner`
- 作业、班会话术、追访问卷、后续教学动作生成

### 更长远扩展

未来新增“短视频作业”“多模态提交”“外部调查平台”时，优先扩：

- `adapter`
- `artifact schema`
- `strategy`

而不是优先新增 agent。只有当任务的认知方式发生明显变化时，再进入 Agent Registry 注册新的 specialist agent。

## 总结

这套设计的核心不是“让系统拥有更多 Agent”，而是：

- 保留现有主链作为控制平面
- 引入结构化 artifact 作为统一中间层
- 让 `Coordinator` 成为唯一前台主 Agent
- 让 specialist agent 通过显式 contract 参与执行
- 让新增输入形式、作业形式和 agent 都能以受控方式扩展

对本项目而言，这比把系统升级成开放式多 Agent 平台更符合当前产品边界，也更利于后续质量治理、评测回放与增量演进。

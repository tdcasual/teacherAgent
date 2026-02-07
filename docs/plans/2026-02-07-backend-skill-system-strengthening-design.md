# Backend Skill System Strengthening Design

## Objective

提升当前后端 skill 系统在“技能命中效果”和“工程质量”两个维度的可用性与可维护性，满足以下验收目标：

- Top1 命中率 >= 85%
- 默认回退率 <= 20%
- 歧义率 <= 10%

本设计聚焦教师后端主链路（`/chat/start -> worker -> /chat/status`），在不破坏现有 API 契约的前提下，强化技能自动选择、可观测性、测试门禁和回滚能力。

## Scope

### In Scope

- `skill_auto_router` 的命中策略升级（配置优先 + 规则兜底）
- `skill.yaml` 路由元数据扩展（阈值、边界匹配）
- 诊断字段统一与报表完善
- 测试体系补齐（单测 + 集成 + 回归样本）
- 失败降级与灰度回滚机制

### Out of Scope

- 引入新模型或重写整个 LLM routing 引擎
- 重构全部 skill prompt 内容
- 前端交互改造

## Current Issues (Static Review)

- 教师侧存在可用 skill 但自动命中路径不完整，导致漏命中风险。
- 当前自动命中置信度基线偏高，缺少最低得分阈值与分差门槛，误命中风险较高。
- 短关键词采用子串匹配，容易被无关词误触发。
- 报表对“空 requested_skill_id”的自动路由统计不完整，难以评估真实自动命中质量。
- 端到端链路测试未充分覆盖 `requested/effective` 一致性与落盘可追踪性。

## Target Design

### 1. Routing Core: Config First, Rule Fallback

将命中逻辑分为两层：

- 第一层：`skill.yaml.routing` 配置打分（主导）
- 第二层：少量硬编码规则（兜底，控制在最小集合）

路由输出统一包含：

- `requested_skill_id`
- `effective_skill_id`
- `reason`
- `confidence`
- `best_score`
- `second_score`
- `threshold_blocked`
- `candidates`（TopN）

### 2. Routing Config Extensions

在 `routing` 增加字段：

- `min_score`: 命中最低分阈值（不达标直接回默认）
- `min_margin`: 第一名与第二名最小分差（不足则标记歧义）
- `confidence_floor`: 基础置信度下限
- `match_mode`: `substring | word_boundary`

规则：

- 短词（如 `ce`）默认必须使用 `word_boundary`。
- 未配置时采用保守默认值，保证旧 skill 不会因缺字段崩溃。

### 3. Ambiguity and Threshold Policy

- 若 `best_score < min_score`：`reason=role_default`，回角色默认技能。
- 若 `best_score - second_score < min_margin`：`reason=ambiguous_auto_rule`，可继续自动选但降置信；必要时走默认。
- 若请求 skill 非法或角色不允许：输出结构化原因（`requested_invalid_*`、`requested_not_allowed_*`）。

### 4. Teacher Coverage Completion

补齐教师侧对 `physics-student-coach` 的自动命中入口，避免“技能允许 teacher 使用但自动路由永远不选中”的结构性漏判。

## Data Flow

统一链路如下：

`chat_start(request.skill_id)`  
-> `job.request.skill_id (requested)`  
-> `compute_chat_reply_sync.resolve_effective_skill(...)`  
-> `req.skill_id = effective`  
-> `run_agent(..., skill_id=req.skill_id)`  
-> `chat_job.done` 写入 `skill_id_requested + skill_id_effective`  
-> teacher/student session meta 写入一致字段  
-> diagnostics `skill.resolve` 可回放

目标是任一请求都能追踪“请求了什么、实际用了什么、为什么这么选”。

## Error Handling and Rollback Matrix

### Error Levels

1. Routing compute layer failure  
2. Policy quality degradation  
3. Release/rollout regression

### Matrix

- Trigger: router exception  
  Detection: `skill.resolve.failed` 突增  
  Auto action: 强制 `role_default`，主链路不中断  
  Manual action: 定位具体 skill 配置或规则  
  Rollback target: 上一版本 routing config  
  Recovery: 失败率回归基线

- Trigger: ambiguity/default rate 超阈值  
  Detection: 15 分钟窗口指标劣化  
  Auto action: 关闭新阈值策略（policy degraded）  
  Manual action: 复盘 Top20 误命中样本  
  Rollback target: 旧策略开关  
  Recovery: `default<=20%` 且 `ambiguous<=10%`

- Trigger: 灰度阶段 top1 跌破 85%  
  Detection: 样本回归与线上影子评估  
  Auto action: 停止放量  
  Manual action: 回滚配置版本并修复  
  Rollback target: 上一稳定版本  
  Recovery: 连续两个窗口满足目标指标

## Testing Strategy

### Unit Tests

- 阈值拦截（`min_score`）
- 分差歧义（`min_margin`）
- 边界匹配（短词误触发防护）
- teacher -> student-coach 路由可达

### Integration Tests

覆盖 `/chat/start -> process_chat_job -> /chat/status`：

- `skill_id_requested` 与输入一致
- `skill_id_effective` 与 runtime 一致
- teacher/session meta 的 skill 字段完整

### Golden Set Regression

建立固定样本集（教师后端问法）并版本化：

- 作业生成
- 学生重点分析
- 路由配置/回滚
- 课堂采集
- 考试分析
- 模糊语义请求

每次改动输出：

- Top1 命中率
- 默认回退率
- 歧义率
- 分类失败样本 TopN

CI gate：不达标即失败，不允许进入主分支。

## Observability and Reporting

扩展 `skill.resolve` 结构化日志，并增强 `scripts/skill_route_report.py`：

- 统计空 `requested_skill_id` 的自动迁移
- 输出 `auto_hit_rate/default_rate/ambiguous_rate`
- 输出 requested->effective 全量迁移矩阵
- 输出按 role、reason、skill 的分布

要求：报表失败不影响在线主链路，只触发告警。

## Delivery Plan

### Milestone 1: Baseline Freeze

- 固化黄金样本与现状指标报告。

### Milestone 2: Router Upgrade

- 上线 `min_score/min_margin/match_mode` 与覆盖补洞。

### Milestone 3: Observability Upgrade

- 日志字段统一 + 报表增强。

### Milestone 4: Quality Gates

- 单测、集成、回归样本全接入 CI 门禁。

## Definition of Done

- 达成指标：Top1 >= 85%，默认 <= 20%，歧义 <= 10%
- 关键链路可追踪 requested/effective/reason
- 回滚机制可在配置层单点触发
- 新增测试与报表在 CI 中稳定通过
- 变更具备灰度放量与自动止损能力

## Implementation Readiness

设计已确认，可进入实现阶段。建议按里程碑分小批提交，确保每一批都可独立回滚与验证。

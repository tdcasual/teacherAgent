# 学生画像优化设计

## 背景

对 279 个学生画像的统计分析显示：
- 89% 的画像只有 `student_id` + `last_updated` + `interaction_notes`
- 0% 的画像有 `recent_weak_kp`、`mastery_by_kp`、`summary`、`practice_history`、`next_focus`
- 仅 10% 有 `student_name`/`class_name`（来自考试导入）

根因：`chat_handlers.py:48` 每次对话只发送 `{student_id, interaction_note}` 给画像更新系统。
`interaction_note` 是原始对话截断拼接，无诊断信息提取。画像基础设施完备但数据管道断裂。

## 问题清单

| # | 问题 | 影响 |
|---|------|------|
| 1 | 对话级更新只记录原文，不提取诊断信息 | 画像无学习数据 |
| 2 | `student_session_finalize.py` 未自动触发 | LLM 摘要能力闲置 |
| 3 | `mastery_by_kp` 从未被写入 | 掌握度追踪缺失 |
| 4 | `interaction_notes` 质量差 | 老师不可读 |
| 5 | `summary` 生成简陋 | 非可读段落 |
| 6 | 考试导入画像与对话画像割裂 | 身份信息缺失 |

## 方案：混合两层更新

### 层 1：对话级规则提取（每轮对话实时触发）

**触发点：** `chat_handlers.py`，在现有 profile update 逻辑处

**新增 `extract_diagnostic_signals(reply_text: str) -> DiagnosticSignals`：**

从 LLM 回复中用正则 + 关键词匹配提取：
- `weak_kp`：匹配"薄弱点/需要加强/建议复习/掌握不够" + 知识点关键词
- `strong_kp`：匹配"掌握得不错/理解正确/答对了/很好" + 知识点
- `misconceptions`：匹配"常见错误/容易混淆/注意区分/典型错误" + 描述
- `next_focus`：匹配"建议/下一步/接下来/重点复习" + 内容

**扩展 payload：**
```python
signals = extract_diagnostic_signals(reply_text)
payload = {
    "student_id": req.student_id,
    "interaction_note": structured_note,  # 结构化摘要
    "weak_kp": ",".join(signals.weak_kp) if signals.weak_kp else "",
    "strong_kp": ",".join(signals.strong_kp) if signals.strong_kp else "",
    "next_focus": signals.next_focus or "",
}
```

**interaction_note 格式优化：**
```
[话题] 牛顿第二定律 | [学生] 答对基础题 | [诊断] 概念理解正确，公式应用需加强
```
截断为 200 字符（当前 900 字符太长）。

**特点：** 零额外 LLM 成本、低延迟、每轮对话都更新。

### 层 2：会话级 LLM 摘要提取（作业完成时触发）

**触发点：** 学生完成作业时（前端发送完成信号）

**流程：**
1. 从 session store 收集本次会话完整对话记录
2. 调用 LLM 提取结构化诊断（复用 `student_session_finalize.py` 核心逻辑）
3. 用 LLM 结果覆盖层 1 的规则提取结果（精度更高）
4. 更新 `mastery_by_kp`（层 1 无法做到）
5. 生成可读 `summary` 段落
6. 检测画像变化，决定是否写入 mem0

**LLM 提取字段（扩展现有 `call_llm_extract`）：**
```json
{
  "weak_kp": ["KP-ID"],
  "strong_kp": ["KP-ID"],
  "medium_kp": ["KP-ID"],
  "misconceptions": [{"kp": "KP-ID", "description": "描述"}],
  "next_focus": "建议",
  "mastery_updates": {"KP-ID": {"accuracy": 0.7, "attempts": 3}},
  "interaction_summary": "可读的一段话摘要",
  "completion_status": "completed|partial|abandoned"
}
```

**特点：** 高精度、全面诊断、异步执行不阻塞用户。

## 优化后的画像 Schema

```json
{
  "student_id": "string (required)",
  "student_name": "string",
  "class_name": "string",
  "created_at": "ISO timestamp",
  "last_updated": "ISO timestamp",
  "aliases": ["string"],

  "recent_weak_kp": ["KP-ID"],
  "recent_strong_kp": ["KP-ID"],
  "recent_medium_kp": ["KP-ID"],
  "next_focus": "string",
  "misconceptions": [
    {"kp": "KP-ID", "description": "描述", "detected_at": "ISO"}
  ],

  "mastery_by_kp": {
    "KP-ID": {"accuracy": 0.7, "attempts": 3, "last_updated": "ISO"}
  },

  "interaction_notes": [
    {"timestamp": "ISO", "note": "结构化摘要", "source": "rule|llm"}
  ],
  "practice_history": [
    {"assignment_id": "", "timestamp": "ISO",
     "status": "completed|partial|abandoned",
     "matched": 0, "graded": 0, "ungraded": 0}
  ],

  "summary": "可读段落（层 2 生成）",
  "import_history": [...]
}
```

**新增字段：**
- `misconceptions` — 记录典型错误模式（KP + 描述 + 时间）
- `interaction_notes.source` — 标记来源（rule 或 llm）
- `practice_history.status` — 作业完成状态
- `mastery_by_kp.last_updated` — 掌握度更新时间

## 实施计划

### 阶段 1：层 1 — 对话级规则提取（核心修复）

| 步骤 | 文件 | 操作 | 风险 |
|------|------|------|------|
| 1.1 | `services/api/chat_support_service.py` | 新增 `extract_diagnostic_signals()` | 低 |
| 1.2 | `services/api/chat_support_service.py` | 优化 `build_interaction_note()` 为结构化摘要 | 低 |
| 1.3 | `services/api/handlers/chat_handlers.py` | 扩展 payload 传入诊断信号 | 低 |
| 1.4 | `skills/.../scripts/update_profile.py` | 支持 `misconceptions`，修复 `mastery_by_kp` | 中 |
| 1.5 | 测试 | 新增 `test_extract_diagnostic_signals.py` | — |

### 阶段 2：参考文档 + Schema 更新

| 步骤 | 文件 | 操作 | 风险 |
|------|------|------|------|
| 2.1 | `references/student_profile.md` | 重写为完整 schema 文档 | 低 |
| 2.2 | `references/profile_update_rules.md` | 增加层 1/层 2 策略说明 | 低 |

### 阶段 3：层 2 — 会话级 LLM 摘要

| 步骤 | 文件 | 操作 | 风险 |
|------|------|------|------|
| 3.1 | `services/api/session_finalize_service.py` | 新建，从脚本提取核心逻辑 | 中 |
| 3.2 | 会话结束 handler | 在作业完成信号处调用 finalize | 中 |
| 3.3 | LLM 提取 prompt | 扩展字段（misconceptions, mastery, status） | 低 |
| 3.4 | `update_profile.py` | 支持 `mastery_by_kp` 增量更新 | 中 |
| 3.5 | `profile_to_mem0.py` | 填充 misconceptions 和 ScoreBand | 低 |
| 3.6 | 测试 | 新增 `test_session_finalize_service.py` | — |

**实施顺序：** 阶段 1 → 阶段 2 → 阶段 3

## 向后兼容

- 现有 279 个画像 JSON 不需要迁移，新字段按需添加
- `update_profile.py` 的现有参数保持不变，新增参数可选
- `interaction_notes` 格式变化不影响已有数据（新旧格式共存）
- 层 1 规则提取是纯新增逻辑，不修改现有提取路径

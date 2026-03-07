# 问卷分析契约（Survey Analysis Contract）

Date: 2026-03-06

## 1. 目标与边界

- 本链路服务于教学 workflow，不是开放式 agent marketplace。
- 前台默认只有 `Coordinator` 对老师可见；specialist agent 只通过内部 handoff 执行。
- V1 聚焦“问卷系统 webhook 推送 -> 证据归一化 -> 班级洞察与教学建议 -> 老师可读报告”。
- V1 输入支持结构化 payload 与非结构化附件（PDF、截图、网页导出）。

- 本域已接入统一分析运行时契约：`docs/reference/analysis-runtime-contract.md`
- 老师读取统一 analysis report plane，survey facade 只做轻量 domain 转发。

## 2. 入口与读取接口

### 2.1 Webhook 入口

- `POST /webhooks/surveys/provider`
- Header: `X-Survey-Signature`
- 成功返回：

```json
{
  "ok": true,
  "job_id": "survey_provider_sub_123",
  "status": "queued",
  "accepted_at": "2026-03-06T10:00:00"
}
```

### 2.2 Teacher 读取接口

- `GET /teacher/surveys/reports?teacher_id=<teacher_id>&status=<optional_status>`
- `GET /teacher/surveys/reports/{report_id}?teacher_id=<teacher_id>`
- `POST /teacher/surveys/reports/{report_id}/rerun`
- `GET /teacher/surveys/review-queue?teacher_id=<teacher_id>`

## 3. 状态机约定

典型状态流转：

`queued -> intake_validated -> normalized -> bundle_ready -> analysis_running -> analysis_ready -> teacher_notified`

低置信度降级流：

`bundle_ready -> review`

失败流：

`* -> failed`

## 4. 核心 Artifact 契约

### 4.1 `survey_evidence_bundle`

`survey_evidence_bundle` 是问卷分析唯一的证据输入对象，结构与 `services/api/survey_bundle_models.py` 对齐：

```json
{
  "survey_meta": {
    "title": "课堂反馈问卷",
    "provider": "provider",
    "submission_id": "sub-1"
  },
  "audience_scope": {
    "teacher_id": "teacher_1",
    "class_name": "高二2403班",
    "sample_size": 35
  },
  "question_summaries": [
    {
      "question_id": "Q1",
      "prompt": "本节课难度如何？",
      "response_type": "single_choice",
      "stats": {"偏难": 12, "适中": 20, "偏易": 3}
    }
  ],
  "group_breakdowns": [
    {
      "group_name": "实验班",
      "sample_size": 20,
      "stats": {"Q1:偏难": 10}
    }
  ],
  "free_text_signals": [
    {
      "theme": "公式推导",
      "evidence_count": 5,
      "excerpts": ["推导太快了"]
    }
  ],
  "attachments": [
    {
      "name": "report.pdf",
      "kind": "pdf",
      "text_length": 168,
      "parse_status": "parsed"
    }
  ],
  "parse_confidence": 0.82,
  "missing_fields": [],
  "provenance": {
    "source": "unstructured",
    "provider": "provider",
    "attachment_count": 1,
    "source_kinds": ["pdf"]
  }
}
```

必看字段：

- `survey_meta`：问卷元信息
- `audience_scope`：教师、班级、样本量边界
- `question_summaries`：核心题目统计
- `free_text_signals`：开放题主题信号
- `parse_confidence`：证据质量总分
- `missing_fields`：缺口说明，供 review 与最终报告展示
- `provenance`：结构化 / 非结构化来源说明

### 4.2 `analysis_artifact`

`analysis_artifact` 是 specialist agent 的标准输出：

```json
{
  "executive_summary": "班级整体能跟上主线，但在公式推导与实验设计上存在集中困惑。",
  "key_signals": [
    {
      "title": "公式推导理解薄弱",
      "detail": "多条证据指向推导节奏过快，学生缺少中间解释。",
      "evidence_refs": ["Q1", "theme:公式推导"]
    }
  ],
  "group_differences": [
    {
      "group_name": "实验班",
      "summary": "实验班对难度感知更高。"
    }
  ],
  "teaching_recommendations": [
    "下节课先用 5 分钟复盘关键推导步骤。",
    "增加一题控制变量的板演例题。"
  ],
  "confidence_and_gaps": {
    "confidence": 0.82,
    "gaps": []
  }
}
```

约束：

- 子 Agent 不直接回老师消息，只返回 `analysis_artifact`
- `confidence_and_gaps` 必须保留，不能只给结论不给证据缺口
- 输出必须可被 render 为 markdown 报告与 teacher report detail

## 5. Review Queue 契约

当 `parse_confidence < SURVEY_REVIEW_CONFIDENCE_FLOOR` 时，结果进入 review queue，而不是直接展示给老师。

`review queue` 项结构：

```json
{
  "report_id": "survey_provider_sub_123",
  "job_id": "survey_provider_sub_123",
  "teacher_id": "teacher_1",
  "class_name": "高二2403班",
  "reason": "low_confidence_bundle",
  "confidence": 0.5,
  "created_at": "2026-03-06T10:05:00"
}
```

## 6. Teacher Report 契约

### 6.1 列表项（summary）

```json
{
  "report_id": "survey_provider_sub_123",
  "teacher_id": "teacher_1",
  "class_name": "高二2403班",
  "status": "teacher_notified",
  "confidence": 0.82,
  "summary": "班级整体能跟上主线，但在公式推导与实验设计上存在集中困惑。",
  "created_at": "2026-03-06T10:00:00",
  "updated_at": "2026-03-06T10:06:00"
}
```

### 6.2 详情（detail）

```json
{
  "report": {
    "report_id": "survey_provider_sub_123",
    "teacher_id": "teacher_1",
    "class_name": "高二2403班",
    "status": "teacher_notified",
    "confidence": 0.82,
    "summary": "班级整体能跟上主线，但在公式推导与实验设计上存在集中困惑。"
  },
  "analysis_artifact": {
    "executive_summary": "班级整体能跟上主线，但在公式推导与实验设计上存在集中困惑。"
  },
  "bundle_meta": {
    "job_id": "survey_provider_sub_123",
    "parse_confidence": 0.82,
    "missing_fields": [],
    "provenance": {
      "source": "unstructured"
    }
  },
  "review_required": false
}
```

## 7. Handoff 约定

Coordinator 内部 handoff 使用 `HandoffContract`，关键字段包括：

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

对于问卷场景：

- `from_agent = coordinator`
- `to_agent = survey_analyst`
- `task_kind = survey.analysis`
- `return_schema.type = analysis_artifact`

## 8. Rollout 与发布门禁

后端环境变量：

- `SURVEY_ANALYSIS_ENABLED`：总开关
- `SURVEY_SHADOW_MODE`：是否 shadow mode 运行
- `SURVEY_BETA_TEACHER_ALLOWLIST`：beta 教师白名单，逗号或空白分隔
- `SURVEY_REVIEW_CONFIDENCE_FLOOR`：进入 review queue 的阈值
- `SURVEY_MAX_ATTACHMENT_BYTES`：单次附件字节上限
- `SURVEY_WEBHOOK_SECRET`：Webhook 签名密钥

前端 feature flag：

- `VITE_TEACHER_SURVEY_ANALYSIS`
- `VITE_TEACHER_SURVEY_ANALYSIS_SHADOW`
- localStorage 覆盖键：`teacherSurveyAnalysis`、`teacherSurveyAnalysisShadow`

发布门禁建议：

1. 先开启 shadow mode，观察报告质量与 review queue 比例。
2. 再通过 `SURVEY_BETA_TEACHER_ALLOWLIST` 逐步扩大老师范围。
3. 低置信度结果默认只进 review queue，不直接触达老师主界面。
4. CI 必须继续通过 backend full suite、survey 相关 targeted tests、teacher build。
5. 具体执行顺序与 go / no-go 检查项见 `docs/operations/survey-analysis-release-checklist.md`。

## 9. V2/V3 扩展原则

- 新输入形态优先扩 `adapter + artifact schema`
- 新任务类型优先扩 `strategy`
- 只有认知职责明显不同，才新增新的 specialist agent
- 保持 Coordinator 为唯一默认前台 Agent

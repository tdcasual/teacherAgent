# 多域分析发布清单（Survey / Class Report / Video Homework）

Date: 2026-03-07

## 1. 适用范围

本 checklist 覆盖三个分析域：

- `survey`
- `class_report`
- `video_homework`

目标不是把系统发布成开放多 Agent 平台，而是在保持 `Coordinator` 单前台入口的前提下，为多域分析能力提供统一的 shadow、beta、release、rollback 门禁。

## 2. 发布前基础验证

### 2.1 后端验证

- [ ] 运行跨域 targeted tests：

```bash
./.venv/bin/python -m pytest -q \
  tests/test_analysis_strategy_eval.py \
  tests/test_analysis_rollout_flags.py \
  tests/test_strategy_selector.py \
  tests/test_docs_architecture_presence.py \
  tests/test_ci_backend_hardening_workflow.py \
  tests/test_analysis_report_service.py \
  tests/test_analysis_report_routes.py \
  tests/test_survey_orchestrator_service.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py
```

- [ ] 运行离线评测：

```bash
./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only
```

通过标准：

- [ ] `expectation_failures == 0`
- [ ] `fixture_count >= 10`
- [ ] `domain_summaries.survey.fixture_count >= 4`
- [ ] `domain_summaries.class_report.fixture_count >= 3`
- [ ] `domain_summaries.video_homework.fixture_count >= 3`
- [ ] `average_required_field_coverage >= 0.80`
- [ ] `average_missing_field_rate <= 0.20`
- [ ] `expectation_failure_reasons == {}`
- [ ] `edge_case_coverage.overall.provider_attachment_noise >= 1`
- [ ] `edge_case_coverage.overall.long_duration_submission >= 1`
- [ ] `edge_case_coverage.overall.low_confidence_parse >= 1`
- [ ] `rollout_recommendations.ready_for_expansion == true`

### 2.2 前端验证

- [ ] 运行 teacher workbench 定向单测：

```bash
cd frontend && npm run test:unit -- \
  apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx \
  apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.test.tsx
```

- [ ] 运行老师端构建：

```bash
cd frontend && npm run build:teacher
```

## 3. 文档核对

- [ ] 统一平台契约文档已更新：`docs/reference/analysis-runtime-contract.md`
- [ ] Survey 契约已明确挂到统一平台：`docs/reference/survey-analysis-contract.md`
- [ ] 当前 checklist 已索引：`docs/operations/multi-domain-analysis-rollout-checklist.md`
- [ ] 历史 survey checklist 仍保留：`docs/operations/survey-analysis-release-checklist.md`
- [ ] B/C 演进实施计划可追溯：`docs/plans/2026-03-07-agent-system-bc-evolution-implementation-plan.md`

## 4. 配置与运行时检查

### 4.1 统一门禁

- [ ] `Coordinator` 仍是唯一默认前台 Agent
- [ ] specialist agent 不直接对老师对话流进行 takeover
- [ ] review queue 仍是低置信度统一出口
- [ ] review queue summary 可见：`unresolved_items`、`reason_counts`、`domains[].unresolved_items`
- [ ] review queue reason taxonomy 已稳定，至少覆盖：`low_confidence`、`missing_fields`、`provider_attachment_noise`、`manual_review`
- [ ] retry / dismiss / escalate 操作已可用，并有 `operator_note` 留痕
- [ ] 老师端读取统一 analysis report plane，而不是 domain 私有页面散落读取

### 4.2 域配置检查

- [ ] Survey: `SURVEY_ANALYSIS_ENABLED=1`（如显式配置为 `0`，survey 新任务应直接失败为 `analysis_domain_disabled`）
- [ ] Survey: `SURVEY_SHADOW_MODE` 与当前阶段一致
- [ ] Survey: `SURVEY_BETA_TEACHER_ALLOWLIST` 已明确
- [ ] Multimodal: `MULTIMODAL_ENABLED=1`
- [ ] Multimodal: `MULTIMODAL_MAX_UPLOAD_BYTES` 已确认
- [ ] Multimodal: `MULTIMODAL_MAX_DURATION_SEC` 已确认
- [ ] Multimodal: `MULTIMODAL_EXTRACT_TIMEOUT_SEC` 已确认
- [ ] `ANALYSIS_DISABLED_DOMAINS` 默认为空；命中后新任务直接失败为 `analysis_domain_disabled`
- [ ] `ANALYSIS_REVIEW_ONLY_DOMAINS` 默认为空；命中后新任务降级到 review queue，reason=`domain_review_only`
- [ ] `ANALYSIS_DISABLED_STRATEGIES` 默认为空；命中后仅对应 strategy 失败为 `analysis_strategy_disabled`
- [ ] `ANALYSIS_DISABLED_DOMAINS` 优先级高于 `ANALYSIS_REVIEW_ONLY_DOMAINS`
- [ ] 统一 review threshold 已确认

### 4.3 运行时证据

- [ ] survey worker / multimodal analyze 路径均可访问
- [ ] 数据目录具备 `survey_reports`、`class_reports`、`video_homework_reports` 写权限
- [ ] 观测日志可查看 target resolver、specialist runtime、orchestrator failed、analyst fallback 事件
- [ ] specialist runtime metrics 可查看 `by_phase` / `by_domain` / `by_strategy` / `by_agent` / `by_reason`
- [ ] `/ops/metrics.metrics.analysis_runtime.counters` 可查看 `run_count` / `fail_count` / `timeout_count` / `invalid_output_count` / `review_downgrade_count` / `rerun_count`
- [ ] `GET /teacher/analysis/metrics` 可用于人工抽查当前 analysis runtime snapshot
- [ ] review queue 日志可导出为 feedback dataset，并保留 `domain` / `strategy_id` / `reason_code` / `disposition` / `operator_note`

## 5. Shadow 发布清单

Shadow 阶段要求：系统要“跑起来”，但不把所有结果当正式结论默认展示。

- [ ] Survey 继续保持 shadow 或受控 beta
- [ ] Class report 先在受控教师 / 班级样本中验证
- [ ] Video homework 先在内部样本或测试教师下验证
- [ ] 每个 domain 至少走一次端到端链路
- [ ] 抽查至少 1 份 survey、1 份 class_report、1 份 video_homework 结果，核对：
  - [ ] `artifact_meta.parse_confidence`
  - [ ] `missing_fields`
  - [ ] `confidence_and_gaps`
  - [ ] `strategy_version` / `prompt_version` / `adapter_version` / `runtime_version`
  - [ ] rerun 响应可同时返回 `previous_lineage` 与 `current_lineage`，便于最小差异比较
  - [ ] rerun / review queue 行为
- [ ] 未发现跨老师数据隔离问题
- [ ] 未发现 specialist 越权输出或伪确定性结论

## 6. Beta 放量清单

- [ ] 仅对白名单教师开放新增域
- [ ] 明确告知老师：当前结论为辅助分析，不自动写回长期真值
- [ ] 每日检查：
  - [ ] report 生成成功率
  - [ ] review queue 增量
  - [ ] rerun 请求量
  - [ ] review feedback summary 是否出现某 domain / reason_code 异常漂移
  - [ ] review feedback dataset 是否出现某 domain / strategy_id 异常集中重试、拒绝或 dismiss
- [ ] 已执行批量 shadow compare：`./.venv/bin/python scripts/build_analysis_shadow_compare_report.py --baseline-dir <baseline_dir> --candidate-dir <candidate_dir>`
  - [ ] shadow / beta 样本中的误报与漏报
- [ ] 每天至少抽查 5 份跨域报告，记录 prompt / parser / adapter 改进点

进入更大范围开放前，需再次确认：

- [ ] beta 期间无持续性 P0 / P1
- [ ] review queue 压力可控
- [ ] rerun 与人工复核流程可工作
- [ ] teacher workbench 没有引发 domain 混淆或错误复用旧对象

## 7. 正式放量清单

- [ ] 统一评测脚本最新输出已归档
- [ ] 发布说明已同步给内部团队
- [ ] 已执行 release-readiness 聚合：`./.venv/bin/python scripts/build_analysis_release_readiness_report.py --contract-check <contract.json> --metrics <metrics.json> --drift-summary <drift.json> --shadow-compare <shadow.json>`
- [ ] on-call、监控、回滚联系人已确认
- [ ] 发布后 30 分钟、2 小时、1 个工作日分别复查一次核心指标
- [ ] 保持 survey / class_report / video_homework 三域的 read path 都通过统一 analysis report plane

## 8. 回滚清单

### 8.1 触发条件

满足任一条件建议立即回滚：

- [ ] 某域报告内容明显失真并已触达老师
- [ ] review queue 激增且无法及时处理
- [ ] 跨教师数据隔离异常
- [ ] teacher workbench 因新域接入导致主界面不可用
- [ ] multimodal 上传 / 抽取链路导致资源耗尽或阻塞

### 8.2 回滚动作

- [ ] 收缩受影响 domain 的功能开关
- [ ] 如需整域熔断，设置 `ANALYSIS_DISABLED_DOMAINS=<domain_id>`（例如 `survey` / `class_report` / `video_homework`）
- [ ] 如需保留 intake 但强制人工复核，设置 `ANALYSIS_REVIEW_ONLY_DOMAINS=<domain_id>`
- [ ] 如需只切断单一策略，设置 `ANALYSIS_DISABLED_STRATEGIES=<strategy_id>`（例如 `survey.teacher.report`）
- [ ] 如需保留后台运行但不前台暴露，则仅保留 shadow 验证
- [ ] 必要时缩回 allowlist
- [ ] 暂停新域流量入口
- [ ] 记录受影响 `report_id` / `submission_id` / `job_id`
- [ ] 通知受影响 beta 老师当前结果暂停使用

### 8.3 回滚后核验

- [ ] 老师主界面不再展示受影响域结果
- [ ] 旧有 chat / assignment / exam 主链功能正常
- [ ] review queue 与历史报告保留以供事后排查
- [ ] 事故记录补充到变更治理文档

## 9. 与 survey checklist 的关系

- Survey 域的专用细则仍以 `docs/operations/survey-analysis-release-checklist.md` 为准
- 本文档负责统一 A/B/C 三域的平台门禁与发布顺序
- 如果新增 domain，应优先补 fixture、`scripts/analysis_strategy_eval.py`、本 checklist 与统一 runtime contract
- 若要支持回归排查，应同步确认可通过 `scripts/replay_analysis_run.py` 读取 report lineage

- [ ] 已执行统一 preflight gate：`./.venv/bin/python scripts/quality/check_analysis_preflight.py --fixtures tests/fixtures --review-feedback <dataset.jsonl> --metrics <metrics.json> --baseline-dir <baseline_dir> --candidate-dir <candidate_dir>`
- [ ] 已生成结构化放量结论：`./.venv/bin/python scripts/quality/build_analysis_rollout_decision.py --artifact-dir <artifact_dir>`
- [ ] 已生成发布简报草稿：`./.venv/bin/python scripts/quality/build_analysis_rollout_brief.py --artifact-dir <artifact_dir>`
- [ ] 已生成 go-live summary 草稿：`./.venv/bin/python scripts/quality/build_analysis_go_live_summary.py --artifact-dir <artifact_dir> --date <YYYY-MM-DD> --release-ref <ref>`
- [ ] 已生成 release notes 草稿：`./.venv/bin/python scripts/quality/build_analysis_release_notes.py --artifact-dir <artifact_dir> --date <YYYY-MM-DD> --release-ref <ref>`
- [ ] 已生成 artifact 索引：`./.venv/bin/python scripts/quality/build_analysis_artifact_manifest.py --artifact-dir <artifact_dir>`
- [ ] 已执行 artifact 完整性 gate：`./.venv/bin/python scripts/quality/check_analysis_artifact_integrity.py --manifest <artifact_dir>/analysis-artifact-manifest.json`
- [ ] `analysis-artifact-integrity.json` 中无 `unknown_dependency`、`build_sequence_mismatch`、`missing_artifact_file`、`missing_dependency_artifact`

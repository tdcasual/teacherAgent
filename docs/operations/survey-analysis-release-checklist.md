# 问卷分析 V1 Release Checklist

Date: 2026-03-07
Scope: `问卷报告分析` 多 Agent V1（`Coordinator + Evidence Pipeline + Survey Analyst Agent`）

## 0. 适用范围

这份 checklist 只适用于当前问卷分析主链路发布：

- webhook 入队
- survey evidence bundle 归一化
- specialist handoff (`survey_analyst`)
- teacher report / review queue
- teacher workbench 最小可见面
- Coordinator 内部 survey handoff

不适用于未来视频作业、问答报告、自托管问卷多 provider 扩展的独立发布。

## 1. 发布角色

- Release owner：负责最终 go / no-go
- Backend owner：负责 webhook、worker、report、review queue
- Frontend owner：负责 teacher workbench 开关与展示
- Prompt / evaluation owner：负责 `analysis_artifact` 输出质量、fixtures 与离线评测
- On-call owner：负责发布后监控、回滚与问题升级

## 2. Go / No-Go 门槛

以下项未满足时，不进入 beta 放量：

- [ ] `SURVEY_ANALYSIS_ENABLED` 处于受控配置，而不是在所有环境默认打开
- [ ] `SURVEY_SHADOW_MODE` 已开启，且已确认 shadow 结果不会直接污染老师主界面
- [ ] `SURVEY_BETA_TEACHER_ALLOWLIST` 已配置或明确为空（只允许 shadow）
- [ ] `SURVEY_REVIEW_CONFIDENCE_FLOOR` 已确认
- [ ] webhook secret、附件大小限制、队列运行方式已确认
- [ ] 契约文档、评测样例、回滚流程都已存在且可访问
- [ ] targeted tests、teacher build、离线评测全部通过
- [ ] 发布当天有明确 owner 值班

## 3. 发布前代码与文档检查

### 3.1 代码验证

- [ ] 运行 survey 后端回归：

```bash
./.venv/bin/python -m pytest -q tests/test_survey_*.py tests/test_docs_architecture_presence.py tests/test_ci_backend_hardening_workflow.py
```

- [ ] 运行离线评测：

```bash
./.venv/bin/python scripts/survey_bundle_eval.py --fixtures tests/fixtures/surveys --json --summary-only
```

通过标准：

- [ ] `expectation_failures == 0`
- [ ] `fixture_count >= 3`
- [ ] `average_required_field_coverage >= 0.80`（建议阈值）
- [ ] `average_missing_field_rate <= 0.20`（建议阈值）

- [ ] 运行前端定向验证：

```bash
cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.test.tsx
```

- [ ] 运行老师端构建：

```bash
cd frontend && npm run build:teacher
```

### 3.2 文档核对

- [ ] 契约文档已更新：`docs/reference/survey-analysis-contract.md`
- [ ] 实施计划仍可追溯：`docs/plans/2026-03-06-survey-multi-agent-implementation-plan.md`
- [ ] 设计文档仍可追溯：`docs/plans/2026-03-06-survey-multi-agent-design.md`
- [ ] 当前 checklist 已挂入索引：`docs/operations/survey-analysis-release-checklist.md`

## 4. 环境配置检查

### 4.1 后端环境变量

- [ ] `SURVEY_ANALYSIS_ENABLED=1`
- [ ] `SURVEY_SHADOW_MODE=1`（第一阶段必须）
- [ ] `SURVEY_WEBHOOK_SECRET` 已配置
- [ ] `SURVEY_MAX_ATTACHMENT_BYTES` 已配置并与上游 provider 限制一致
- [ ] `SURVEY_REVIEW_CONFIDENCE_FLOOR` 已确认
- [ ] `SURVEY_BETA_TEACHER_ALLOWLIST` 已明确

### 4.2 前端功能开关

- [ ] `VITE_TEACHER_SURVEY_ANALYSIS` 与后端策略一致
- [ ] `VITE_TEACHER_SURVEY_ANALYSIS_SHADOW` 与后端 `SURVEY_SHADOW_MODE` 一致
- [ ] 未依赖本地 `localStorage` override 作为正式发布配置

### 4.3 运行时检查

- [ ] survey worker 已启动
- [ ] 队列 backend（inline / RQ）与目标环境一致
- [ ] 数据目录具备 `survey_jobs`、`survey_reports`、`survey_review_queue.jsonl` 写权限
- [ ] 观测日志可查看 webhook accepted / orchestrator failed / analyst fallback 事件

## 5. Shadow 发布清单

Shadow 阶段要求：系统要“跑起来”，但不默认把结果作为老师主界面的正式结论。

- [ ] 仅开启 shadow mode，不开放给所有老师
- [ ] 选定 1 个受控班级或测试教师作为 shadow 样本
- [ ] 用真实 webhook 数据走一次端到端链路
- [ ] 确认 `survey_jobs`、`bundle.json`、`survey_reports`、`survey_review_queue.jsonl` 都有可追溯数据
- [ ] 抽查至少 3 份 shadow 报告，核对：
  - [ ] `bundle_meta.parse_confidence`
  - [ ] `missing_fields`
  - [ ] `analysis_artifact.confidence_and_gaps`
  - [ ] 教学建议没有越权结论或伪确定性表述
- [ ] 记录 review queue 占比、低置信度主因、典型解析缺口

建议满足以下条件后再进入 beta：

- [ ] shadow 样本中没有 blocker 级错误（入队失败、报告无法打开、前端崩溃）
- [ ] review queue 占比可接受（建议 < 25%，若高于此值先优化解析与阈值）
- [ ] 未发现明显误导性建议

## 6. Beta 放量清单

- [ ] `SURVEY_BETA_TEACHER_ALLOWLIST` 仅包含明确通知过的老师
- [ ] 告知 beta 老师：当前结果为辅助洞察，不直接写入长期真值
- [ ] 准备支持答疑渠道与问题收集模板
- [ ] 每日检查以下项目：
  - [ ] webhook 成功率
  - [ ] report 生成成功率
  - [ ] review queue 增量
  - [ ] rerun 请求量
  - [ ] 老师侧反馈中的误报/漏报案例
- [ ] 每天抽查至少 5 份 beta 报告，记录质量问题与 prompt / parser 改进项

进入更大范围开放前，需再次确认：

- [ ] beta 期间无持续性 P0 / P1
- [ ] review queue 压力可控
- [ ] rerun 与人工复核流程可工作
- [ ] 前端展示没有引发老师误解“这是最终事实写回系统”

## 7. 正式放量清单

- [ ] 明确是否关闭 `SURVEY_SHADOW_MODE`
- [ ] 明确是否扩大 / 清空 `SURVEY_BETA_TEACHER_ALLOWLIST`
- [ ] 发布说明已同步到内部团队
- [ ] On-call 值班、监控、回滚联系人已确认
- [ ] 发布后 30 分钟、2 小时、1 个工作日分别复查一次核心指标

正式放量后重点观察：

- [ ] 低置信度报告是否被正确送入 review queue
- [ ] Coordinator 问卷 handoff 没有破坏原有 teacher chat 主链
- [ ] teacher workbench 页面加载、刷新、rerun 入口正常
- [ ] 没有出现跨老师数据读取问题

## 8. 回滚清单

### 8.1 触发条件

满足任一条件建议立即回滚：

- [ ] webhook 大面积失败
- [ ] survey worker 持续失败或阻塞
- [ ] 报告内容明显失真并已触达老师
- [ ] 跨教师数据隔离异常
- [ ] teacher workbench 因 survey 功能导致主界面不可用

### 8.2 回滚动作

- [ ] 将 `SURVEY_ANALYSIS_ENABLED=0`
- [ ] 如需保留后台运行但不前台暴露，则保持后端关闭前台入口或仅保留 `SURVEY_SHADOW_MODE=1`
- [ ] 将 `VITE_TEACHER_SURVEY_ANALYSIS=0`
- [ ] 必要时收缩 `SURVEY_BETA_TEACHER_ALLOWLIST`
- [ ] 暂停上游 webhook 推送或切换到沙箱来源
- [ ] 记录受影响的 `job_id` / `report_id`
- [ ] 通知 beta 老师当前结果暂停使用

### 8.3 回滚后核验

- [ ] 老师主界面不再展示问卷分析入口或结果
- [ ] 旧有 chat / assignment / exam 主链功能正常
- [ ] 没有新的 survey report 继续对外可见
- [ ] review queue 与历史报告保留以供事后排查
- [ ] 事故记录补充到变更与风险文档

## 9. 发布证据留存

发布完成后，建议在同一天（2026-03-07 或实际发布日期）留存：

- [ ] 测试命令输出
- [ ] 离线评测 JSON 输出
- [ ] 代表性 report 截图或导出
- [ ] review queue 抽样记录
- [ ] beta 老师名单 / 时间窗口
- [ ] 回滚联系人与操作路径

## 10. 建议的发布顺序

1. 本地 / 预发验证通过
2. 打开后端 `SURVEY_ANALYSIS_ENABLED=1` + `SURVEY_SHADOW_MODE=1`
3. 前端仅在受控环境展示入口
4. 跑 shadow 观察
5. 配置 `SURVEY_BETA_TEACHER_ALLOWLIST`
6. 小范围 beta
7. 复盘问题并修正
8. 再决定是否扩大范围或正式开放

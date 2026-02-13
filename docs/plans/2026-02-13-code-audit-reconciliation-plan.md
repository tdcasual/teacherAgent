# 代码审计对账修复计划（2026-02-13）

## 1. 目标与输入

本计划用于对齐两份审计结论与当前代码真实状态，避免重复修复、遗漏高风险项。

- 审计输入 A（pre-merge）:
  - `/Users/lvxiaoer/Documents/New project/.merge-backups/2026-02-13-code-audit-findings.premerge.md`
- 审计输入 B（持续修复后）:
  - `/Users/lvxiaoer/Documents/New project/docs/plans/2026-02-13-code-audit-findings.md`
- 当前代码基线（已包含近期修复）:
  - `main@e41660f`

## 2. 约束与假设

1. `chart.exec` 默认 `trusted` 为明确业务约束，本计划不修改该默认行为。
2. 本计划只覆盖“仍未闭环”或“部分闭环需补强”的项；已完成项不重复实施。
3. 状态判定以当前代码为准，不以旧报告文本状态为准。

## 3. 方案比较（Brainstorming）

### 方案 A：全量重扫 290 条再重排
- 优点：最完整，理论上不漏。
- 缺点：成本高、重复工作多，且会打断当前修复节奏。

### 方案 B：仅修 pre-merge Top 10
- 优点：推进快。
- 缺点：会忽略“Top10 外但仍高风险”的已知缺口（例如跨模块原子写、图表资源鉴权）。

### 方案 C（推荐）：对账矩阵 + 风险批次
- 做法：先做“已修复/部分修复/未修复/接受风险”矩阵，再按 P0/P1/P2 分批。
- 结论：兼顾准确性与推进速度，最适合当前阶段。

## 4. 对账矩阵（关键问题）

| 主题 | pre-merge 结论 | 当前状态 | 证据（代码） | 处理策略 |
|---|---|---|---|---|
| 路由鉴权缺失（student/skills/exam/assignment） | AUTH-H-2~H-9 | 已修复 | `services/api/routes/student_history_routes.py:10` `services/api/routes/skill_crud_routes.py:11` `services/api/routes/assignment_upload_routes.py:11` `services/api/routes/exam_query_routes.py:11` | 关闭，不重复修复 |
| Persona 原子写/并发锁/字段约束 | H-1/H-2/H-4/H-5 + M | 已修复 | `services/api/teacher_persona_api_service.py:79` `services/api/teacher_persona_api_service.py:87` `services/api/student_persona_api_service.py:84` `services/api/student_persona_api_service.py:92` | 关闭，不重复修复 |
| 头像上传整包读入内存 | PERF-6 | 已修复 | `services/api/routes/teacher_persona_routes.py:19` `services/api/routes/student_persona_routes.py:25` | 关闭，不重复修复 |
| 轮询无超时/无中断 | FE-L-10 衍生 | 已修复 | `frontend/apps/shared/visibilityBackoffPolling.ts:91` | 关闭，不重复修复 |
| 速率限制桶无界增长 | PERF-13 | 已修复 | `services/api/rate_limit.py:62` `services/api/rate_limit.py:76` | 关闭，不重复修复 |
| 列表接口无分页 | PERF-1/PERF-2 衍生 | 已修复 | `services/api/assignment_catalog_service.py:91` `services/api/exam_catalog_service.py` | 关闭，不重复修复 |
| CI action 未 SHA pin | CI-1/CI-2 | 已修复 | `.github/workflows/*.yml`（已无 `@v*`） | 关闭，不重复修复 |
| Gemini native `{model}` 未插值 | H-17 | 未修复 | `config/model_registry.yaml:70` + `llm_gateway.py:343` | 纳入 P0 |
| subprocess 无 timeout | PERF-9/PERF-10 | 未修复 | `services/api/core_utils.py:51` `services/api/exam_utils.py:285` | 纳入 P0 |
| KaTeX `style` 允许导致 CSS 注入面 | FE-H-1 | 未修复 | `frontend/apps/shared/markdown.ts:110` | 纳入 P0 |
| 备份容器挂载项目根 `./:/workspace` | INFRA-D-3/D-4 | 未修复 | `docker-compose.yml:177` `docker-compose.yml:218` `docker-compose.yml:257` | 纳入 P1 |
| `chart.exec` 默认 trusted + 沙箱绕过面 | H-20~H-22 | 接受风险（受约束） | `services/api/chart_executor.py:716` `services/common/tool_registry.py:438` | 记录风险 + 补偿控制（P2） |
| 前端 CSRF（旧结论） | FE-H-2/FE-H-3 | 已降级为“认证模型问题” | `frontend/apps/shared/authFetch.ts:39` `frontend/apps/student/src/main.tsx:9` `frontend/apps/teacher/src/main.tsx:9` + `services/api/auth_service.py:217` | 不做传统 CSRF 改造，做认证基线守护（P1） |
| 非原子写跨模块遗留 | H/M 多处 | 部分未修复 | `services/api/assignment_upload_parse_service.py:83` `services/api/assignment_upload_parse_service.py:222` `services/api/chat_attachment_service.py:87` | 纳入 P0/P1 |

## 5. 新一轮修复批次

### Batch R0（P0，先修，1-1.5 天）

目标：消除当前仍可直接触发的高危/高可用性风险。

1. 修复 Gemini native endpoint 模板插值
- 改动：在 gateway 构建 Target 时对 endpoint 做 `{model}` 替换（仅 gemini-native 生效）。
- 验收：新增用例覆盖 `endpoint=/models/{model}:generateContent` 生效路径。

2. 修复关键 subprocess timeout 缺失
- 改动：`run_script()` 与 `exam_utils._parse_xlsx_with_script()` 增加有限 timeout（可配置，默认 300s）。
- 验收：新增超时模拟测试，验证超时时返回可诊断错误。

3. 修复 markdown CSS 注入面
- 改动：`katexSchema` 去除通用 `style`，或引入严格 CSS 属性白名单过滤器（禁止 `url()`、`position:fixed` 等）。
- 验收：新增前端安全测试，覆盖恶意 style payload 被剥离。

4. 修复剩余关键非原子写
- 改动：`assignment_upload_parse_service` 与 `chat_attachment_service` 的 JSON/text 持久化改为原子写工具。
- 验收：中断写入回归（模拟异常）不产生损坏文件。

### Batch R1（P1，次优先，1 天）

目标：收紧平台默认安全基线，降低运维与后续回归风险。

1. 备份容器最小挂载面
- 改动：去除 `./:/workspace`，改为白名单目录挂载（`data/uploads/output/scripts/backup`）。
- 验收：备份任务可执行，且容器不可读取仓库其它敏感文件。

2. 认证模型“opt-in”防回归机制
- 改动：新增路由鉴权覆盖测试（扫描路由并校验需显式 `require_principal/resolve_*_scope` 或豁免名单）。
- 验收：新增未鉴权路由时 CI 直接失败。

3. 补齐图表资源与 ops 端点的鉴权策略
- 改动：为 `/charts/*`、`/chart-runs/*`、`/ops/*` 增加角色或 owner 约束（若业务要求公开则显式豁免并文档化）。
- 验收：跨身份访问被拒绝；合法访问不回归。

### Batch R2（P2，策略层，0.5 天）

目标：在“默认 trusted 不可改”前提下，增加可审计补偿控制。

1. `chart.exec` 风险补偿（不改默认）
- 增加审计日志：记录 `execution_profile`、调用来源、关键包安装行为。
- 增加可选策略开关：生产可配置为仅允许特定角色/来源使用 `trusted`。
- 增加告警：`trusted` 执行命中高风险模式时告警（不阻断）。

2. 安全基线文档化
- 在审计文档中新增“接受风险清单”，明确 owner、复审时间、退出条件。

## 6. 验收与回归清单

每批至少执行：

```bash
python3 -m pytest \
  tests/test_llm_gateway.py \
  tests/test_chart_exec_tool.py \
  tests/test_chat_attachment_service.py \
  tests/test_assignment_upload_parse_service.py \
  tests/test_security_auth_hardening.py \
  tests/test_docker_security_baseline.py -q

npm --prefix frontend run typecheck
```

针对批次补充：

- R0：新增/扩展 `llm_gateway`、markdown sanitize、subprocess timeout、原子写相关测试。
- R1：新增路由鉴权守卫测试、backup 运行基线测试。
- R2：新增 trusted 调用审计日志测试（或最小集成验证）。

## 7. 交付节奏与状态同步

1. 先执行 R0，完成后更新：
   - `/Users/lvxiaoer/Documents/New project/docs/plans/2026-02-13-code-audit-findings.md`
2. 再执行 R1，补齐基线与回归防护。
3. 最后执行 R2，完成风险补偿与文档闭环。

---

## 8. 本计划中的“明确不做”

1. 不修改 `chart.exec` 默认 `trusted`。
2. 不重复执行已闭环的大批量鉴权回填与上传限额改造。
3. 不在本轮引入重型基础设施改造（如全面 secrets/vault 迁移），仅做可落地增量改进。

---

## 9. 执行进展（更新于 2026-02-13）

- R0（P0）: 已完成
  - Gemini `{model}` endpoint 插值修复
  - subprocess timeout 加固
  - markdown sanitize（KaTeX style）收敛
  - assignment/chat 附件关键写入原子化
- R1（P1）: 已完成
  - backup 容器移除 `./:/workspace`，改为最小白名单挂载
  - 新增路由鉴权守卫回归测试（显式 guard 或 allowlist）
  - `/charts/*`、`/chart-runs/*`、`/ops/*` 增加鉴权角色约束
- R2（P2）: 已完成
  - 已完成：`chart.exec` 审计日志、`trusted` 高风险模式告警、可选 trusted 来源/角色策略开关
  - 已完成：审计文档新增“接受风险清单”（owner/复审时间/退出条件）

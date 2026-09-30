# teacherAgent 严格评分地板计划（≥8.5，目标 9）

| 字段 | 值 |
| --- | --- |
| 日期 | 2026-09-06 |
| 状态 | Draft v2（Codex round-1 FAIL 已吸收） |
| 基线 | `main` @ `c529714` |
| 不兼容点 | 教师读路径改为 SQL-primary；09-05 的 D2/D3 backlog 取消。不重开 exam。 |
| 臃肿约束 | 不拆 `auth_registry_service.py`；不加 Grafana；不加新 structure-test 文件；不新增前端应用 |

## Overview

九项从严评分必须各自 ≥8.5（Grok 与 Codex 都评，取低分否决）。杠杆是：**同一可见性谓词 + SQL 权威读 + 一次性和解回填 + 可执行交接 + 分支保护**。不靠涨预算、不靠断言源码字符串刷分。

## Codex round-1 吸收

1. SQL-primary **不是**「丢掉未迁 JSON」。`assignment.store.ensure()` 在缺 schema v2 时已经一次性 JSON→SQL。本波教师改 SQL 读之后：v2 前的遗产随 `ensure()` 进入表；**v2 之后**盘上有 JSON、表中无行 = crash 孤儿，教师/学生都不可见（与现学生 vis 一致）。Rollout 要求 `ensure()` 对账：表行数 ≥ 目录 meta 数或显式列出孤儿 id。
2. Bus factor：不能发明第二 GitHub 账号。用**过程冗余**代替人：`main` 必过 CI+Teacher E2E+Mobile E2E（branch protection）；H 变更要求 Codex review 纪要进 PR；交接脚本进 CI。目标 8.5 =「第二人按手册+脚本能接管」，不是「编制变两人」。
3. Compose loopback 已在 `docker-compose.yml` 与 `test_leftover_survey_and_catalog.py`。本波把它提升为独立 `tests/test_compose_publish_host.py`，避免埋在 leftover 文件里。
4. 前端 PR 改为**边界**：`App.tsx` 不得展开 workbench/session 的 80 个字段；把对象传入子模块。行数回落是副作用，不是目标。
5. 分页：`(updated_at DESC, assignment_id DESC)`，cursor 为 `updated_at|assignment_id`。
6. 可见性：单一函数 `assignment_row_visible(*, role, teacher_id, for_today)` 给 catalog / progress / student today 共用。

## Key Decisions

| ID | 决定 |
| --- | --- |
| KD-1 | 读路径一次切 SQL-primary，不做 dual-read 过渡 PR |
| KD-2 | confirm 仍双写 JSON（heal）；list/today/progress 不以目录存在为 vis |
| KD-3 | App 抽取是依赖方向（对象下传），不是为过行数测试 |
| KD-4 | Bus factor 用 branch protection + 交接脚本 + Codex review 纪要，不伪造 CODEOWNER |
| KD-5 | 双评分取低；任一项 &lt;8.5 则改代码或改计划再评 |
| KD-6 | `ensure()` v2 是唯一自动回填；之后孤儿只 heal，不扫盘 |

## Persist

### 回填 / 孤儿

| 状态 | 教师 list | 学生 today |
| --- | --- | --- |
| 表有 published 行 | 可见（owner 匹配） | 可见（名册+published） |
| 仅 JSON、v2 未记 | `ensure()` 导入后同上 | 同上 |
| 仅 JSON、v2 已记 | 不可见 | 不可见 |
| 表 archived | 可见给 owner | today 不可见，history 可见 |

对账命令（PR-1 测试调用同一函数）：`reconcile_assignment_sql(data_dir) -> {sql_count, json_meta_count, orphan_ids}`。CI 单测覆盖孤儿 id 非空时 list 不含它们。

### Store API

```
list_assignment_rows(conn, *, teacher_id: str | None, limit, cursor) -> (rows, next_cursor)
# WHERE teacher_id = ? if teacher_id else all
# ORDER BY updated_at DESC, assignment_id DESC
# indexes already: idx_assignments_owner (teacher_id, visibility_status, date)

row_visible(row, *, role, actor_id, for_today: bool) -> bool
```

Teacher 非 admin：`row.teacher_id == actor_id` 且 vis in {published, archived, draft}（自己的草稿可见）。
Student today：vis == published 且 id in published set（现逻辑）。
Admin：可 list 全部；不在本波改 claim。

`question_count`：`questions.csv` 缺则 0，**不**因此把 vis 改成 hidden（blob 损坏可观测，不静默下架）。Progress 404 仅当 SQL 无行。

### 锁

confirm 继续在 `BEGIN IMMEDIATE` **之外**算 expected_students。测试：线程 A 持有 assignment 连接 IMMEDIATE，线程 B `compute_expected_students` 必须在 3s timeout 内返回（现实现不在锁内连库）。禁止第二连接在 IMMEDIATE 里 `CREATE TABLE`。

## Frontend

`useTeacherWorkbenchState()` 的返回值整对象传给 layout/workbench，App 不再逐字段解构。学生侧把 markdown cache + viewport effects 收入已有 hooks。行为测试：现有 TeacherAppLayout / StudentTodayHome unit 必须绿。行数 &lt;800/&lt;770 是副作用断言。

## Ops / 治理

- `tests/test_compose_publish_host.py`：compose 三端口默认 `127.0.0.1`。
- `scripts/maintainer_recovery_check.sh`：`python -c` 探 AUTH 三态文档锚点 + compose 断言 + `ensure` import；CI backend-quality 一步调用它（失败即红）。
- 若 `gh api` 允许：`main` required checks = CI、Teacher E2E、Mobile Session Menu E2E。不允许则文档写明缺口，评分 ops 不得报 9。

## Non-Goals

filter-repo、生产密钥轮换、假第二 CODEOWNER、Grafana、mypy strict 全树、拆 registry、停 JSON 双写、live compose E2E 进 PR 必跑。

## Alternatives

1. D2 再 D3 — 两次分叉，拒绝。
2. 拆 registry — 体积与认证风险，拒绝。
3. 涨 App 预算 — 放弃治理，拒绝。
4. Dual-read miss→JSON — 把孤儿变回可见，拒绝。

## Security

Owner 过滤在 SQL `WHERE teacher_id=?`，不是读出后再滤（防漏）。无 teacher_id 的行不出现在教师 list。

## Rollout

无 flag。部署：起 API 即 `ensure()`；对账测试锁死孤儿语义。回滚：revert 读路径，JSON 仍在。

## PR Plan

**PR-1** `feat(persist): SQL-primary catalog/progress + shared visibility + reconcile`

- `assignment/store.py`（list_assignment_rows, reconcile, 稳定排序）
- `assignment/visibility.py` 或 store 上的 `row_visible`
- `assignment_catalog_service.py`、`assignment_progress_service.py`
- 测试：JSON-only+v2 → 教师不可见；confirm 后可见；owner 隔离；分页稳定；reconcile orphan_ids
- 风险 H，TDD

**PR-2** `test: sqlite lock + compose publish host + recovery script`

- confirm 锁回归；`test_compose_publish_host.py`；`scripts/maintainer_recovery_check.sh` 接入 ci.yml
- 风险 M

**PR-3** `refactor(frontend): pass workbench/session objects, do not explode fields in App`

- teacher/student App + 接收对象的子模块
- 现有 unit 必须绿；行数预算保持 800/770
- 风险 L

**PR-4** `docs: handoff, ARCHIVE, CONTRIBUTING H-review, permission dates`

- 含 AUTH_REQUIRED 三态、同库锁、孤儿语义
- 风险 L

并行：1∥3，2∥4。

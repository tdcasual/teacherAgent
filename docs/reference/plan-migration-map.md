# 历史 Plan 迁移映射

- 最后更新：2026-08-26
- 当前权威修复方案：`docs/plans/2026-08-26-audit-remediation-design.md`（审计修复权威，**不是**运行时契约）
- `docs/plans/` 其余稿为历史；稳定结论在 `docs/reference/`、`docs/explain/`、`docs/operations/`。
- 目的：标记已提炼为稳定文档的内容，降低重复查阅成本。未全部归档的历史稿接受为 AR-L1。

2026-08-22 审计修复草案已被 2026-08-26 方案取代，不再作为修复依据。

| 历史文档 | 提炼状态 | 新承接文档 |
|---|---|---|
| `docs/plans/2026-08-26-audit-remediation-design.md` | 当前权威（审计修复方案） | 本文件为修复权威；运行时契约仍见 `docs/reference/` |
| `docs/plans/2026-02-13-auth-token-password-design.md` | 已提炼（核心认证模型） | `docs/reference/auth-and-token-model.md` |
| `docs/plans/2026-02-13-code-audit-findings.md` | 部分提炼（风险与接受项） | `docs/reference/risk-register.md` |
| `docs/plans/2026-02-13-code-audit-findings.md`（上传限额相关） | 已提炼（资源防护基线） | `docs/reference/upload-resource-guardrails.md` |
| `docs/plans/2026-02-13-code-audit-findings.md`（锁竞态相关） | 已提炼（并发策略说明） | `docs/explain/locking-and-idempotency-rationale.md` |
| `docs/plans/2026-02-22-backend-quality-hardening-report.md` | 已提炼（演进说明） | `docs/explain/backend-quality-hardening-overview.md` |
| `docs/plans/2026-02-14-admin-auth-docker-bootstrap-design.md` | 已提炼（操作入口） | `docs/how-to/admin-manage-teachers-tui.md` + `docs/reference/auth-and-token-model.md` |
| `docs/plans/2026-02-15-admin-tui-efficiency-enhancement-design.md` | 已提炼（实操） | `docs/how-to/admin-manage-teachers-tui.md` |

## 后续批次建议
1. 剩余 `docs/plans/` 历史稿不删；AR-L1 接受直至 migration-map 覆盖仍被运行时引用的稿，其余可归档。
2. 前端 prettier 仅覆盖 `apps/shared` 的接受项见 AR-L3，退出条件是纳入 teacher/student 并一次 format。
3. 为高频 plan 增加“已提炼到哪篇文档”的反向链接。

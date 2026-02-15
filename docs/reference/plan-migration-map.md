# 历史 Plan 迁移映射

- 最后更新：2026-02-15
- 目的：标记 `docs/plans/` 中已提炼为稳定文档的内容，降低重复查阅成本。

| 历史文档 | 提炼状态 | 新承接文档 |
|---|---|---|
| `docs/plans/2026-02-13-auth-token-password-design.md` | 已提炼（核心认证模型） | `docs/reference/auth-and-token-model.md` |
| `docs/plans/2026-02-13-code-audit-findings.md` | 部分提炼（风险与接受项） | `docs/reference/risk-register.md` |
| `docs/plans/2026-02-13-code-audit-findings.md`（上传限额相关） | 已提炼（资源防护基线） | `docs/reference/upload-resource-guardrails.md` |
| `docs/plans/2026-02-13-code-audit-findings.md`（锁竞态相关） | 已提炼（并发策略说明） | `docs/explain/locking-and-idempotency-rationale.md` |
| `docs/plans/2026-02-22-backend-quality-hardening-report.md` | 已提炼（演进说明） | `docs/explain/backend-quality-hardening-overview.md` |
| `docs/plans/2026-02-14-admin-auth-docker-bootstrap-design.md` | 已提炼（操作入口） | `docs/how-to/admin-manage-teachers-tui.md` + `docs/reference/auth-and-token-model.md` |
| `docs/plans/2026-02-15-admin-tui-efficiency-enhancement-design.md` | 已提炼（实操） | `docs/how-to/admin-manage-teachers-tui.md` |

## 后续批次建议
1. 继续提炼作业/考试上传链路与限流策略到 `docs/reference/`。
2. 继续提炼多租户与运行时隔离策略到 `docs/explain/`。
3. 为高频 plan 增加“已提炼到哪篇文档”的反向链接。

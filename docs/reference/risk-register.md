# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-03-03
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`

## 已关闭风险
### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 默认执行档位曾保持 `trusted`，高于 `sandboxed` 风险基线。
- 关闭说明：
  1. 默认执行档位已切换到 `sandboxed`。
  2. `trusted` 仅在显式声明 `execution_profile=trusted` 且策略允许时生效。
  3. 审计日志仍记录执行上下文（来源/角色/调用信息）用于持续追踪。
- Owner：后端平台负责人
- 关闭日期：2026-03-03
- 验证证据：
  1. `services/api/chart_executor.py` 默认 profile 逻辑改为 `sandboxed`。
  2. `services/common/tool_registry.py` 中 `chart.exec.execution_profile.default` 改为 `sandboxed`。

## 持续关注项
1. 上传链路资源上限（数量/大小/MIME）必须持续防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/plans/2026-02-13-code-audit-findings.md`

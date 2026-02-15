# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-02-15
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`

## 当前接受风险
### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 默认执行档位保持 `trusted`（业务约束），高于 `sandboxed` 风险基线。
- 当前补偿控制：
  1. 审计日志记录执行上下文（来源/角色/调用信息）。
  2. 对 `trusted` 场景增加告警与策略收敛开关。
  3. 通过来源和角色白名单逐步缩小 `trusted` 触发面。
- Owner：后端平台负责人
- 下次复审日期：2026-03-13
- 退出条件：
  1. 默认执行档位切换到 `sandboxed`，或
  2. `trusted` 被强制限制在白名单来源与角色并稳定运行一个迭代。

## 持续关注项
1. 上传链路资源上限（数量/大小/MIME）必须持续防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/plans/2026-02-13-code-audit-findings.md`

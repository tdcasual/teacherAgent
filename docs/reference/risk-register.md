# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-08-26
- 主要来源：`docs/plans/2026-08-26-audit-remediation-design.md`

## 进行中风险

### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 的 LLM 工具 schema 仍暴露 `trusted`；空 allowlist 仍放行 trusted；sandbox 可读 `data/`。
- 状态：进行中（已从已关闭重开）
- 关闭说明：修复 PR 进行中。
- Owner：后端平台
- 下次复审日期：2026-11-26
- 退出条件：LLM 不可选 trusted；空 allowlist deny；schema 无 `execution_profile`；FS roots 不含 `data/`。

### RISK-MCP-UNAUTH-001
- 风险描述：MCP 空密钥时 `/mcp` 匿名放行，compose 将 `9000:9000` 发布到全接口，脚本路径缺少白名单。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：空密钥 503；loopback；脚本白名单。

### RISK-ADMIN-BOOTSTRAP-001
- 风险描述：`data/auth/admin_bootstrap.txt` 含已提交明文管理员口令，且未被 gitignore。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：git 无明文；gitignore；口令与 `AUTH_TOKEN_SECRET` 已轮换。

### RISK-UPLOAD-UNBOUNDED-001
- 风险描述：`/upload` 与 `/student/submit` 无共享数量/字节限额；后缀门不完整；`/upload` 无角色门。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：`/upload` 与 `/student/submit` 共享限额 + 后缀门 + `/upload` 角色门。

### RISK-REDIS-LRU-JOBS-001
- 风险描述：Redis `allkeys-lru` 256mb 与 RQ、`ChatRedisLaneStore` 共用，满时可能静默驱逐 job/lane key。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：Runtime
- 下次复审日期：2026-11-26
- 退出条件：单实例 noeviction；lane 与 RQ 同实例。

### RISK-WORKER-HEALTH-001
- 风险描述：worker healthcheck 可能自匹配 argv；upload/exam/survey/chat enqueue 超时与重试策略不一致。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：Runtime
- 下次复审日期：2026-11-26
- 退出条件：healthcheck 匹配进程；upload/exam/survey timeout+retry；chat timeout-only。

### RISK-AUTH-REQUIRED-AUTZ-001
- 风险描述：`AUTH_REQUIRED=0` 在已有 principal 时也关闭授权；production 未忽略显式 `AUTH_REQUIRED=0`。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：有 principal 必须授权；production 忽略 `AUTH_REQUIRED=0`。

### RISK-MASTERKEY-CRYPTO-001
- 风险描述：代码内存在默认 master key；加密算法为自制流密码，AES-GCM 迁移另 PR。
- 状态：进行中（接受算法债）
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：无代码内默认 key；AES-GCM 迁移另 PR。

### RISK-SLO-WINDOW-001
- 风险描述：SLO 文档声称 30 天窗口，实现为进程内短窗口样本，文档与实现不一致。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：文档与实现窗口一致。

### RISK-OPENAPI-EXPOSE-001
- 风险描述：FastAPI `/docs`、`/redoc`、`/openapi.json` 在 production 或 `AUTH_REQUIRED=1` 时仍可被已认证非 admin 刮取 schema。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：production/`AUTH_REQUIRED=1` 时 `/docs` 404。

## 已关闭风险

（暂无。`RISK-CHART-TRUSTED-001` 于 2026-08-26 复审重开。）

## 持续关注项
1. 上传链路资源上限（数量/大小/MIME）必须持续防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/plans/2026-08-26-audit-remediation-design.md`

# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-08-26
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`；接受项按 2026-08-26 审计增补

## 进行中风险

### RISK-MCP-UNAUTH-001
- 风险描述：MCP 空密钥时 `/mcp` 匿名放行，compose 将 `9000:9000` 发布到全接口，脚本路径缺少白名单。
- 状态：进行中
- 关闭说明：修复 PR 进行中。
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：空密钥 503；loopback；脚本白名单。
- 补偿控制：空密钥 `POST /mcp` 返回 503；compose 要求 `MCP_API_KEY` 且绑定 `127.0.0.1:9000`；脚本与用户路径白名单；`/health` 保持匿名仅因 loopback。

### RISK-ADMIN-BOOTSTRAP-001
- 风险描述：历史提交将 `data/auth/admin_bootstrap.txt` 明文 admin 密码纳入 git；克隆/fork 仍持有该 blob，直至运营完成口令与密钥轮换。
- 状态：补偿控制已落地，待运营轮换
- Owner：平台
- 下次复审日期：2026-11-26
- 退出条件：生产已轮换 admin 密码与 `AUTH_TOKEN_SECRET`（及 `AUTH_TOKEN_SECRET_FILE` 内容）；旧 Bearer 全部失效
- 补偿控制：`.gitignore` 覆盖 `data/auth/admin_bootstrap.txt` 与 `data/auth/*bootstrap*`；该文件已从 git 索引取消跟踪；不 rewrite `main` 历史。退出仍要求运营完成轮换。

### RISK-UPLOAD-UNBOUNDED-001
- 风险描述：`/upload` 与 `/student/submit` 无共享数量/字节限额；后缀门不完整；`/upload` 无角色门。
- 状态：补偿控制已落地，待合并复核后关闭
- 关闭说明：共享 20/20MB/80MB（`upload_limits.py` 仅数字）；后缀唯一录取门；MIME 不单独放行也不否决合法后缀；`/upload` `require_principal`；submit/OCR 走 `save_upload_file` 且同名不覆盖。
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

### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 的 LLM 工具 schema 曾暴露 `trusted`；空 allowlist 曾放行 trusted；sandbox 曾可读 `data/`。
- 状态：已关闭
- 关闭说明：LLM 不可选 trusted；空 allowlist deny；exam `template` 保留；trusted 需 `CHART_EXEC_TRUSTED_ENABLED=1` + 非空 source/role allowlist 且 source 非 tool_loop/chat/llm；schema 无 `execution_profile`；FS roots 不含 `data/`；sandboxed cwd=`output_dir`。
- Owner：后端平台
- 下次复审日期：2026-11-26
- 退出条件：LLM 不可选 trusted；空 allowlist deny；schema 无 `execution_profile`；FS roots 不含 `data/`。

## 已接受风险
### AR-L1
- 风险描述：`docs/plans/` 含审计修复方案在内的历史计划稿存量大，本轮不删除、不全部归档。
- 状态：已接受
- Owner：文档
- 下次复审日期：2026-11-26
- 退出条件：migration-map 覆盖仍被运行时引用的稿；其余可归档目录。
- 补偿控制：W5-P11 已更新 `docs/reference/plan-migration-map.md` 与 `docs/INDEX.md`，声明 `docs/plans/` 非运行时契约；`docs/plans/2026-08-26-audit-remediation-design.md` 为审计修复权威。

### AR-L3
- 风险描述：prettier 只扫描 `frontend/apps/shared`，teacher/student 未纳入。
- 状态：已接受
- Owner：前端
- 下次复审日期：2026-11-26
- 退出条件：prettier 纳入 `apps/teacher` + `apps/student` 且一次 format PR。
- 补偿控制：CI `frontend-quality` 对 teacher/student 跑 eslint / typecheck / build；`format:check` 至少覆盖 shared。

## 持续关注项
1. 上传链路资源上限（数量/大小/MIME）必须持续防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/reference/plan-migration-map.md`
- `docs/plans/2026-02-13-code-audit-findings.md`
- `docs/plans/2026-08-26-audit-remediation-design.md`

# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-08-22
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`；条目按 2026-08-22 全量审计重开与增补

## 进行中 / 重开

### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 的 LLM schema 曾暴露 `execution_profile=trusted`，空 allowlist 放行 trusted；2026-03-03 纸面关闭说明已失效。
- 状态：修复 PR 进行中
- Owner：后端平台负责人
- 下次复审日期：2026-11-22
- 退出条件：LLM 不可选 trusted；空 allowlist deny；exam template 保留；trusted 需 ENABLED + 非空 source/role allowlist 且 source 非 tool_loop/chat/llm
- 补偿控制：LLM schema 删除 `execution_profile`（`additionalProperties: false` 拒绝模型传入）；tool_loop/chat/llm/`tool_dispatch.chart.exec` 强制 sandboxed 并扫描；空 allowlist 或未设 `CHART_EXEC_TRUSTED_ENABLED` 拒绝 trusted；exam 内部仍走 `template` 并扫描；H 变更 2 人评审。

### RISK-MCP-UNAUTH-001
- 风险描述：MCP 空密钥无认证，且 `0.0.0.0:9000` 可公网暴露；工具含写操作与任意脚本执行。
- 状态：修复 PR 进行中
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：空密钥 503；loopback；脚本白名单
- 补偿控制：空密钥 `POST /mcp` 返回 503；compose 要求 `MCP_API_KEY` 且绑定 `127.0.0.1:9000`；脚本与用户路径白名单；`/health` 保持匿名仅因 loopback；H 变更 2 人评审。

### RISK-ADMIN-BOOTSTRAP-001
- 风险描述：历史提交将 `data/auth/admin_bootstrap.txt` 明文 admin 密码纳入 git；克隆/fork 仍持有该 blob，直至运营完成口令与密钥轮换。
- 状态：补偿控制已落地，待运营轮换
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：生产已轮换 admin 密码与 `AUTH_TOKEN_SECRET`（及 `AUTH_TOKEN_SECRET_FILE` 内容）；旧 Bearer 全部失效
- 补偿控制：`.gitignore` 覆盖 `data/auth/admin_bootstrap.txt` 与 `data/auth/*bootstrap*`；该文件已从 git 索引取消跟踪；不 rewrite `main` 历史。退出仍要求运营完成轮换。

### RISK-UPLOAD-UNBOUNDED-001
- 风险描述：`/upload` 与 `/student/submit` 无数量/大小/MIME 上限；仅部分 exam/assignment 流有限额。
- 状态：修复 PR 进行中
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：共享 exam 限额 + MIME
- 补偿控制：exam/assignment start 已有 20/20MB/80MB；H 变更 2 人评审。

### RISK-REDIS-LRU-JOBS-001
- 风险描述：Redis `allkeys-lru` 256mb 可能驱逐 RQ 与 chat lane key，导致静默丢 job。
- 状态：修复 PR 进行中
- Owner：Runtime
- 下次复审日期：2026-11-22
- 退出条件：单实例 noeviction；lane 与 RQ 同实例；不迁 LRU
- 补偿控制：chat idempotency 走文件系统而非 Redis；H 变更 2 人评审。

### RISK-WORKER-HEALTH-001
- 风险描述：worker healthcheck 与进程命令行自匹配，enqueue 无 timeout/retry。
- 状态：修复 PR 进行中
- Owner：Runtime
- 下次复审日期：2026-11-22
- 退出条件：healthcheck 匹配进程；enqueue 有 timeout/retry
- 补偿控制：upload/exam 已有 job id 幂等；H 变更 2 人评审。

### RISK-AUTH-REQUIRED-AUTZ-001
- 风险描述：`AUTH_REQUIRED=0` 在已有 principal 时也关掉授权，production 未忽略该开关。
- 状态：修复 PR 进行中
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：有 principal 必须授权；production 忽略 AUTH_REQUIRED=0
- 补偿控制：compose 默认 `AUTH_REQUIRED=1`；H 变更 2 人评审。

### RISK-MASTERKEY-CRYPTO-001
- 风险描述：自制流密码（非 AEAD）且代码内默认 master key；本波接受算法债。
- 状态：修复 PR 进行中
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：无代码内默认 key；AES-GCM 迁移另 PR
- 补偿控制：生产缺 `MASTER_KEY` 已启动失败；本波只去掉硬编码默认值。

### RISK-SLO-WINDOW-001
- 风险描述：SLO 文档声称 30 天窗口，实现是进程内最近 5000 样本、多 worker 不聚合。
- 状态：修复 PR 进行中
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：文档与实现窗口一致
- 补偿控制：`/ops/metrics` 与 `/ops/slo` 需 `service`/`admin` principal；不对外承诺虚假 SLA。

## 已接受风险

### AR-F30
- 风险描述：exam/assignment `application.py` 仍透传编排，本轮接受残余债。
- 状态：已接受
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：见 Wave 5 增量抽取
- 补偿控制：`docs/architecture/module-boundaries.md` 禁止新增透传；H/M 变更 2 人评审。

### AR-L1
- 风险描述：`docs/plans/` 历史计划稿存量大，本轮接受未全部归档。
- 状态：已接受
- Owner：文档
- 下次复审日期：2026-11-22
- 退出条件：migration-map 覆盖运行时仍引用的稿
- 补偿控制：稳定文档以 `docs/reference/` 与 `docs/operations/` 为准。

### AR-L3
- 风险描述：prettier 只扫描 `frontend/apps/shared`，teacher/student 未纳入。
- 状态：已接受
- Owner：前端
- 下次复审日期：2026-11-22
- 退出条件：prettier 扩到 teacher/student
- 补偿控制：`frontend-quality` 仍跑 typecheck / lint / build。

### AR-L4
- 风险描述：`.github/CODEOWNERS` 仅 `@tdcasual` 单维护者。
- 状态：已接受
- Owner：平台
- 下次复审日期：2026-11-22
- 退出条件：第二维护者写入 CODEOWNERS
- 补偿控制：H 变更 2 人评审与 PR 模板补评审缺口。

## 已关闭风险

当前无已关闭条目。2026-03-03 纸面关闭的 RISK-CHART-TRUSTED-001 已于 2026-08-22 重开。

## 持续关注项
1. 上传限额尚未覆盖 `/upload` 与 `/student/submit`（见 RISK-UPLOAD-UNBOUNDED-001）；补齐后必须防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/plans/2026-02-13-code-audit-findings.md`

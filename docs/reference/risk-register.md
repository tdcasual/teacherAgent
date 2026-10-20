# 安全风险与接受清单（当前）

- 适用角色：管理员、平台负责人
- 最后验证日期：2026-09-01
- 主要来源：`docs/plans/2026-02-13-code-audit-findings.md`；2026-08-26 审计；2026-09-01 作业内核复审

## 进行中风险

### RISK-ADMIN-BOOTSTRAP-001
- 风险描述：历史提交将 `data/auth/admin_bootstrap.txt` 明文 admin 密码纳入 git；克隆/fork 仍持有该 blob，直至运营完成口令与密钥轮换。
- 状态：补偿控制已落地，待运营轮换
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：生产已轮换 admin 密码与 `AUTH_TOKEN_SECRET`（及 `AUTH_TOKEN_SECRET_FILE` 内容）；旧 Bearer 全部失效
- 补偿控制：`.gitignore` 覆盖 `data/auth/admin_bootstrap.txt` 与 `data/auth/*bootstrap*`；该文件已从 git 索引取消跟踪；不 rewrite `main` 历史。退出仍要求运营完成轮换。

### RISK-CHART-SANDBOX-RESIDUAL-001
- 风险描述：C2 收紧 chart sandbox（去掉 DATA_DIR env、扫描并补丁 `os.open`/`os.fdopen`、LLM schema 去掉 `auto_install`/`packages`）后，pathlib.Path.read_text/open、`io.open`、shutil.copyfile、glob、mmap、os.mkdir/rename 仍可能绕过 `builtins.open` 补丁读取 DATA_DIR。C2 不是 jail；本条目保持开放。
- 状态：开放
- Owner：后端
- 下次复审日期：2026-12-01
- 退出条件：Landlock/seccomp 或等价隔离落地，且残余旁路测试不再作为接受项。
- 补偿控制：扫描拦截 `os.open`/`os.fdopen`/`os.read(` / `os.write(` / `os.replace`；guard 补丁 `builtins.open` 与 `os.open`/`os.fdopen`；LLM 不可选 `auto_install`/`packages`；tool_loop / `tool_dispatch.chart.exec` 强制 `auto_install=False` 并忽略 packages。接受测试 `test_pathlib_read_text_data_dir_is_accepted_residual` 锁死残余。

### RISK-ADMIN-WEB-001
- 风险描述：空 `TENANT_ADMIN_KEY` 时仍挂 multi-tenant dispatcher，可能把 `/health` 或管理面绑到非 default_app。
- 状态：已关闭（补偿控制）
- 关闭说明：空 key 时 `_build_runtime_entrypoint` 只返回 `default_app`。非空 key 必须设置 `TENANT_DATA_BASE_DIR`，否则启动失败。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：空 key 不挂 dispatcher；非空 key 强制数据根目录。

### RISK-GHCR-VITE-URL-001
- 风险描述：GHCR bake 将 `VITE_API_URL=http://127.0.0.1:8000` 编进前端。校园局域网需另建 compose/`VITE_API_URL`。
- 状态：已接受
- Owner：运维
- 下次复审日期：2026-12-01
- 退出条件：校园镜像单独 bake；文档写明 GHCR 仅 loopback。
- 补偿控制：`docs/getting-started/quickstart.md` 记录 bake URL。

### RISK-PIP-AUDIT-IGNORES-001
- 风险描述：`check_backend_dep_audit.sh` 忽略 PYSEC-2026-161、PYSEC-2026-248、PYSEC-2026-249、PYSEC-2026-2280、PYSEC-2026-2281、PYSEC-2026-2636。原因：FastAPI 0.128.7 caps starlette<1；mem0 1.0.3。
- 状态：开放
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：升级 FastAPI/starlette/mem0 后去掉对应 ignore。


### RISK-ASSIGNMENT-DUALWRITE-001
- 风险描述：进度数字仍 compute-primary；表双写。非 SQL-primary GET。
- 状态：开放
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：discussion/submission 迁表且 GET 以 SQL 为权威（目标 2026-12-01）。
- 补偿控制：folder 缺失不 2PC、不 mkdir；JSON 失败 ROLLBACK；submit/grade 双写失败不影响 GET compute。

## 已关闭风险

### RISK-STUDENT-ASSIGNMENT-DETAIL-001
- 风险描述：学生 `GET /assignment/{id}` 原样返回 `questions.csv` 全列（含 `answer_ref`）以及 meta 中的 `answer_files` / `expected_students`。
- 状态：已关闭
- 关闭说明：`public_student_assignment_detail` 对学生题目字段做 allowlist，并省略 `answer_files`、`expected_students`、`student_ids`。教师详情保持完整列。
- 回滚：revert 该提交后学生详情会再次带出答案引用。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：学生详情无 `answer_ref` / 答案列 / `answer_files`；教师详情仍含完整列。

### RISK-STEM-REF-READ-001
- 风险描述：作业详情与陪练题干读取将 `stem_ref` 解析为绝对路径或 `APP_ROOT` 相对路径，未套用作业目录 / 题库 jail，可读取 jail 外文本。
- 状态：已关闭
- 关闭说明：catalog 与 context 读取共用 `resolve_readable_stem_ref`（作业目录 jail 或 `data/question_bank` jail，含 symlink resolve）。jail 外路径不注入 `stem_text`。
- 回滚：revert 该提交后详情/context 会再次按 APP_ROOT 裸读。
- Owner：后端
- 下次复审日期：2026-12-01
- 退出条件：jail 外 `stem_ref`（含 symlink）不返回文件内容；作业目录与题库内题干仍可读。

### RISK-AUTH-CHANGE-ME-001
- 风险描述：example 使用 `change_me` 占位；compose `${:?}` 只拒绝空值；`validate_auth_secret_policy` 接受任意非空 `AUTH_TOKEN_SECRET`，生产可带着众所周知占位符启动。
- 状态：已关闭
- 关闭说明：example 必填密钥留空；生产拒绝空密钥与字面量 `change_me`。
- 回滚：revert 该提交后 example 再次带 `change_me`，生产策略再次放行占位符。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：example 必填密钥为空；生产 `AUTH_TOKEN_SECRET=change_me` 启动失败。

### RISK-BACKUP-AUTH-OMIT-001
- 风险描述：备份 include 列表不含 `data/auth` 与 `data/student_submissions`，registry SQLite 与学生提交物不进归档。
- 状态：已关闭
- 关闭说明：两个目录加入 domain 列表；live `*.sqlite3` 经 `sqlite3.Connection.backup` 快照后再入 tar，不直接打包正在写入的数据库文件。
- 回滚：revert 该提交后备份再次省略 auth/submissions，并恢复直接 tar 数据库文件。
- Owner：运维
- 下次复审日期：2026-12-01
- 退出条件：domain 列表含 `data/auth` 与 `data/student_submissions`；registry SQLite 经 backup API 快照后单独追加进 tar（live `*.sqlite3` 排除不得吞掉 overlay）。

### RISK-TOKEN-VERSION-SET-PASSWORD-001
- 风险描述：`set_password` 过去只更新密码哈希、不递增 `token_version`，且师生 Bearer 缺 `tv` 仍放行，改密后旧 access token 继续有效。
- 状态：已关闭
- 关闭说明：改密与密码哈希同一 UPDATE 递增 `token_version` 并签发新 access token；teacher/student/admin 缺 `tv` 一律 401 `token_revoked`。无 tv 的旧师生 Bearer 需重新登录。
- 回滚：revert 代码（旧代码会再次忽略缺 tv，且仍接受带 tv 的新 token）。若生产已发出新 token 后必须回滚：旋转 `AUTH_TOKEN_SECRET` / `AUTH_TOKEN_SECRET_FILE`。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：改密递增 `token_version` 并签发新 token；缺 `tv` 的师生/管理员 Bearer 一律 401 `token_revoked`。

### RISK-MASTERKEY-CRYPTO-001
- 风险描述：加密算法为自制流密码（非 AEAD）。
- 状态：已关闭
- 关闭说明：新写入使用 AES-256-GCM（版本字节 0x02）；旧 XOR 密文（0x01）仍可解密一次。无代码内默认 master key。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：无代码内默认 key；AES-GCM 迁移另 PR。

### RISK-COMPOSE-PUBLISH-001
- 风险描述：compose 默认把 API `8000` 与前端 `3001`/`3002` 发布到全部网卡。
- 状态：已关闭
- 关闭说明：默认 `PUBLISH_HOST=127.0.0.1`。校内局域网显式设 `PUBLISH_HOST=0.0.0.0`。
- Owner：运维
- 下次复审日期：2026-12-01
- 退出条件：公网部署经 TLS 反代且 `PUBLISH_HOST=127.0.0.1`；或防火墙不转发 8000/3001/3002。


### RISK-MCP-UNAUTH-001
- 风险描述：MCP 空密钥时 `/mcp` 匿名放行，compose 将 `9000:9000` 发布到全接口。
- 状态：已关闭
- 关闭说明：空密钥 503；compose `127.0.0.1:9000` + `MCP_API_KEY:?`；脚本白名单。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：空密钥 503；loopback；脚本白名单。

### RISK-UPLOAD-UNBOUNDED-001
- 风险描述：`/upload` 与 `/student/submit` 无共享数量/字节限额；`/upload` 无角色门。
- 状态：已关闭
- 关闭说明：共享 20/20MB/80MB；后缀门；`/upload` `require_principal`。学生提交另加作业 published + 花名册 + 在读校验。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：`/upload` 与 `/student/submit` 共享限额 + 后缀门 + `/upload` 角色门。

### RISK-REDIS-LRU-JOBS-001
- 风险描述：Redis `allkeys-lru` 驱逐 RQ 与 chat lane。
- 状态：已关闭
- 关闭说明：`--maxmemory-policy noeviction`；loopback bind。
- Owner：Runtime
- 下次复审日期：2026-12-01
- 退出条件：单实例 noeviction；lane 与 RQ 同实例。

### RISK-WORKER-HEALTH-001
- 风险描述：worker healthcheck 自匹配 argv。
- 状态：已关闭
- 关闭说明：心跳文件 healthcheck；chat timeout-only；upload/profile Retry。
- Owner：Runtime
- 下次复审日期：2026-12-01
- 退出条件：healthcheck 匹配进程；chat timeout-only。

### RISK-AUTH-REQUIRED-AUTZ-001
- 风险描述：`AUTH_REQUIRED=0` 在已有 principal 时也关闭授权。
- 状态：已关闭
- 关闭说明：生产忽略 `AUTH_REQUIRED=0`；作业 ACL 在有 principal 时始终校验 owner/scope。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：有 principal 必须授权；production 忽略 `AUTH_REQUIRED=0`。

### RISK-SLO-WINDOW-001
- 风险描述：SLO 文档声称 30 天窗口，实现为进程内短窗口。
- 状态：已关闭
- 关闭说明：文档已改为诚实窗口；`/ops/metrics.prom` 走 service/admin。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：文档与实现窗口一致。

### RISK-OPENAPI-EXPOSE-001
- 风险描述：FastAPI `/docs` 在 production 或 `AUTH_REQUIRED=1` 时仍可刮 schema。
- 状态：已关闭
- 关闭说明：production/`AUTH_REQUIRED=1` 卸载 `/docs` `/redoc` `/openapi.json`。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：production/`AUTH_REQUIRED=1` 时 `/docs` 404。

### RISK-CHART-TRUSTED-001
- 风险描述：`chart.exec` 的 LLM 工具 schema 曾暴露 `trusted`；空 allowlist 曾放行 trusted；sandbox 曾可读 `data/`。
- 状态：已关闭
- 关闭说明：LLM 不可选 trusted；空 allowlist deny；FS roots 不含 `data/`。
- Owner：后端平台
- 下次复审日期：2026-12-01
- 退出条件：LLM 不可选 trusted；空 allowlist deny；schema 无 `execution_profile`；FS roots 不含 `data/`。

### RISK-PHYSICS-SKILL-SURFACE-001
- 风险描述：`physics-*` skill 曾对所有老师出现在 `GET /skills` 与自动路由中。
- 状态：已关闭（产品面）
- 关闭说明：全员只暴露作业三件套。`packs/subjects/<id>/pack.yaml` 的 `skill_affiliates` 仅在该老师名册含对应 `subject_id` 时并入 catalog / `resolve_skill` / auto-router。未登录或未任教物理的老师不会路由到 `physics-*`。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：名册无物理任教时产品面无 `physics-*`；有物理任教时可显式/自动选用附属 skill。

### RISK-COV-REBASELINE-20260905
- 风险描述：删除 leftover analysis/multimodal 后 coverage 分母变化，原 84% 地板不再是诚实测量。
- 状态：已关闭
- 关闭说明：2026-09-05 plan A4 将 CI `--cov-fail-under` 重基到实测 TOTAL 的 floor 85%；禁止 omit 保 84。
- Owner：平台
- 下次复审日期：2026-12-01
- 退出条件：CI floor 等于删除后实测 `floor(TOTAL)`。

## 已接受风险
### AR-L1
- 风险描述：`docs/plans/` 含审计修复方案在内的历史计划稿存量大，本轮不删除、不全部归档。
- 状态：已接受
- Owner：文档
- 下次复审日期：2026-12-01
- 退出条件：migration-map 覆盖仍被运行时引用的稿；其余可归档目录。
- 补偿控制：W5-P11 已更新 `docs/reference/plan-migration-map.md` 与 `docs/INDEX.md`，声明 `docs/plans/` 非运行时契约；`docs/plans/2026-08-26-audit-remediation-design.md` 为审计修复权威。

### AR-L3
- 风险描述：prettier 只扫描 `frontend/apps/shared`，teacher/student 未纳入。
- 状态：已关闭
- 关闭说明：2026-09-06 B3：`format:check` 改为 `apps/**/*.{ts,tsx,css}`，并对 teacher/student 做一次 format。
- Owner：前端
- 下次复审日期：2026-12-01
- 退出条件：prettier 纳入 `apps/teacher` + `apps/student` 且一次 format PR。

## 持续关注项
1. 上传链路资源上限（数量/大小/MIME）必须持续防回退。
2. 锁与并发处理策略需防止重复执行与幽灵任务。
3. 凭据与权限变更必须同步到审计与回归测试。
4. 公网部署不得直接发布 8000/3001/3002。

## 相关文档
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`
- `docs/reference/plan-migration-map.md`

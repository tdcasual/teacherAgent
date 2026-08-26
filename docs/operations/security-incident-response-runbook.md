# Security Incident Response Runbook

Last updated: 2026-08-26

## 目标

在安全事件发生时，确保响应过程具备：

1. 快速止损
2. 证据保全
3. 可追溯复盘

## 事件分级

### SEV-1（严重）

- 凭据泄露、权限绕过、生产数据外泄、核心流程不可用。
- 要求：
  1. 立即启动应急流程；
  2. 15 分钟内完成首次通报；
  3. 优先止损，后补业务恢复细节。

### SEV-2（高）

- 可利用漏洞已公开但未确认被利用，或关键服务有明显异常趋势。
- 要求：
  1. 1 小时内完成风险评估与处置计划；
  2. 当天给出补丁或临时缓解。

### SEV-3（中/低）

- 需修复但暂未形成直接生产风险。
- 要求：
  1. 纳入正常迭代；
  2. 记录到风险登记并设置复审日期。

## 标准处置流程

1. 发现与确认
   - 收集事件来源（告警、用户报告、审计日志）。
   - 确认影响范围（模块、角色、租户、时间窗口）。
2. 立即止损
   - 回滚最近变更、关闭高风险入口、轮换相关凭据。
   - 必要时启用降级开关保持核心服务可用。
3. 证据保全
   - 导出相关审计日志、CI 记录、部署记录。
   - 保留最小复现材料，避免污染证据链。
4. 修复与验证
   - 先补回归测试，再提交修复。
   - 在 PR 中附验证证据与回滚方案。
5. 沟通与复盘
   - 输出时间线、根因、影响评估、改进行动项。
   - 更新风险登记和相关治理文档。

## 响应职责

1. Incident Commander（值守负责人）
   - 决策分级、协调响应节奏、统一对外沟通口径。
2. Technical Owner（技术负责人）
   - 制定修复方案并执行验证。
3. Scribe（记录员）
   - 记录时间线、操作命令、关键证据链接。

## 凭据泄露（SEV-1）

已提交到 git 的口令、token、密钥一律视为已泄露。取消跟踪、gitignore、删除工作区文件都 **不能** 从历史或既有克隆中抹去 blob；不要在本波 rewrite `main` 历史。只有轮换才能让旧凭据失效。

### 已提交的 admin bootstrap 明文

适用：`data/auth/admin_bootstrap.txt` 曾入库（`username=admin` 与明文 `password=`）。关联 `RISK-ADMIN-BOOTSTRAP-001`。

1. 立即将该历史 admin 口令视为已泄露。所有克隆/fork 仍持有 blob，直到轮换完成。
2. **必须**轮换生产/校内部署的 admin 密码。可登录则 `POST /auth/admin/login` 后改密；否则设置新的 `ADMIN_PASSWORD`，删除 volume 内 `admin_auth` 行与 `${DATA_DIR}/auth/admin_bootstrap.txt` 后重启（仅当确认无其他 admin）。
3. **生产必做**：同时轮换 `AUTH_TOKEN_SECRET` 以及 `AUTH_TOKEN_SECRET_FILE` 内容。旧 Bearer 全部失效，学生、教师、管理员必须重新登录。
4. 确认 `.gitignore` 覆盖 `data/auth/admin_bootstrap.txt` 与 `data/auth/*bootstrap*`，且该文件不再被 git 跟踪。不要把新密码提交进仓库。
5. 证据保全：记录发现时间、受影响部署/克隆、轮换完成时间；导出相关审计与部署记录。
6. 操作细节见 `docs/how-to/auth-and-account-troubleshooting.md` 与 `SECURITY.md`。

### 通用凭据泄露步骤

1. 判定分级为 SEV-1，15 分钟内首次通报。
2. 止损：轮换泄露凭据与由其签发的会话（admin 口令、`AUTH_TOKEN_SECRET`、相关 token）。
3. 评估影响面：哪些环境克隆过仓库、哪些账号仍在使用旧口令/旧 Bearer。
4. 修复验证：回归测试覆盖「不再跟踪明文」；运营确认轮换已落地。
5. 更新 `docs/reference/risk-register.md` 的状态、补偿控制与退出条件。

## 检查清单

1. 凭据是否已轮换（如 token secret、管理员口令）。
2. 高风险入口是否已临时封禁或限流。
3. 审计日志是否覆盖事件窗口并可导出。
4. 修复是否包含自动化回归测试。
5. 风险登记是否更新复审日期与退出条件。
6. 若为仓库明文泄露：gitignore / 取消跟踪已落地，且生产已轮换 admin 密码与 `AUTH_TOKEN_SECRET`。

## 关联文档

1. `SECURITY.md`
2. `CONTRIBUTING.md`
3. `docs/reference/risk-register.md`
4. `docs/operations/change-management-and-governance.md`

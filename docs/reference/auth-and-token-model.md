# 认证与令牌模型（稳定参考）

- 适用角色：管理员、老师、开发者
- 最后验证日期：2026-08-26
- 主要来源：`docs/plans/2026-02-13-auth-token-password-design.md`（稳定结论提炼）；`AUTH_REQUIRED` 真值表见审计修复 F18/F50

## 核心模型
1. 学生与教师账号定位（identify）与认证分离。
2. 登录成功后统一签发 Bearer token。
3. token 与密码仅存 hash，不存明文。
4. 老师可按学生/班级/全量重置学生密码并查看新默认密码。
5. 管理员可重置 token/密码并查看审计记录。

## `AUTH_REQUIRED` 语义
`AUTH_REQUIRED=0` 只允许**匿名**访问非豁免路由（本地 DX），**不**关闭授权。只要请求带了可解析的 Bearer principal，一律执行角色与作用域检查。

| `AUTH_REQUIRED` | 环境 | pytest | principal | 结果 |
| --- | --- | --- | --- | --- |
| `1` | 任意 | 任意 | 无 | 非豁免路径 **401**；角色不匹配 **403** |
| `0` | 非 production | 任意 | 无 | 非豁免路径允许匿名（例如 `/teacher/*` 不因缺 token 一律 401） |
| `0` | 非 production | 任意 | 有，越权 | **403**（不得短路） |
| `0` | production（`APP_ENV`/`ENV` 为 `prod` 或 `production`） | 未设 | — | 视为 `AUTH_REQUIRED=1` |
| 未设 | 非 production | 未设 | — | 保持 `bool(AUTH_TOKEN_SECRET)` |
| 未设 | production | 未设 | — | 开启认证 |
| 未设 | production | `PYTEST_CURRENT_TEST` | — | 测试自动关（不得被「production 视 0 为 1」打断） |

生产忽略显式 `AUTH_REQUIRED=0` 时，缺失 `AUTH_TOKEN_SECRET` 仍 fail-closed。

## 租户管理 `/admin/`（不是公网匿名）
- `_auth_exempt_path` 对 `path.startswith("/admin/")` 豁免 **Bearer**，因为 `MultiTenantDispatcher` 的 tenant admin 使用 `X-Admin-Key`，不是 access token。
- 该豁免 **不等于** 公网匿名：`/admin/tenants` 等业务接口无 `X-Admin-Key` 时返回 401/403，而不是 200 业务数据。Bearer 不能代替 `X-Admin-Key`。
- `OPTIONS` 预检走 `_is_exempt_auth_request`，不写入 `_auth_exempt_path`。
- default_app（非 dispatcher）不得新增 `/admin/` 业务路由；若出现，必须有独立 key 检查。

## 学生认证流程
1. `name + class_name` identify。响应 `candidate_id` 为不透明短时句柄（`cid_<32hex>`，TTL 10 分钟），不含稳定 `student_id`。
2. 仅支持 `password` 登录；`credential_type=token` 返回 `invalid_credential_type`。登录入参使用 identify 返回的不透明 `candidate_id`；成功后 token `sub` 仍是内部 `student_id`。
3. 密码由老师端发放或重置，学生端不再提供 token 登录入口。
4. 遗留 `POST /student/verify` 需要 teacher/admin；响应同样省略 `student_id`。

## 教师认证流程
1. `name` identify。
2. 若同名歧义，必须补 `email` 去歧义。
3. 唯一定位后使用 token/密码登录。

## 老师端学生密码管理
- 入口：`POST /auth/teacher/student/reset-passwords`
- 支持范围：`student` / `class` / `all`
- 入参：
  - `scope`
  - `student_id`（`scope=student`）
  - `class_name`（`scope=class`）
  - `new_password`（可选；缺省则生成默认密码）
- 出参：返回命中的学生列表及 `temp_password`（仅本次返回明文）。

## 管理员能力
- 重置学生/教师 token。
- 导出学生/教师 token。
- 管理教师账号状态（启用/禁用、重置密码、创建教师）。
- 名册 CSV：`POST /auth/admin/students/import` 只写 `student_auth`，不自动 enroll。
- 编班走 `POST /auth/admin/roster` 与 `POST /auth/admin/enrollments/enroll-class`。
- TUI 管理入口：`admin_manager`（容器 trusted-local 模式）。

## 失效与轮换
- 账号凭据重置后，`token_version` 递增。
- 历史 Bearer token 在版本校验时失效（典型错误：`token_revoked`）。

## 错误语义（常见）
- `invalid_credential`：凭据错误。
- `invalid_credential_type`：凭据类型不被该角色支持（学生仅 `password`；教师可用 `token`/`password`）。
- `password_not_set`：未设置密码但使用密码登录。
- `disabled`：账号被禁用。
- `locked`：失败次数触发临时锁定。
- `multiple`：身份定位歧义（需补班级或邮箱）。

## 相关文档
- `docs/how-to/student-login-and-submit.md`
- `docs/how-to/admin-manage-teachers-tui.md`
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`

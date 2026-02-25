# 认证与令牌模型（稳定参考）

- 适用角色：管理员、老师、开发者
- 最后验证日期：2026-02-25
- 主要来源：`docs/plans/2026-02-13-auth-token-password-design.md`（稳定结论提炼）

## 核心模型
1. 学生与教师账号定位（identify）与认证分离。
2. 登录成功后统一签发 Bearer token。
3. token 与密码仅存 hash，不存明文。
4. 老师可按学生/班级/全量重置学生密码并查看新默认密码。
5. 管理员可重置 token/密码并查看审计记录。

## 学生认证流程
1. `name + class_name` identify。
2. 仅支持 `password` 登录。
3. 密码由老师端发放或重置，学生端不再提供 token 登录入口。

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
- 管理教师账号状态（启用/禁用、重置密码）。
- TUI 管理入口：`admin_manager`（容器 trusted-local 模式）。

## 失效与轮换
- 账号凭据重置后，`token_version` 递增。
- 历史 Bearer token 在版本校验时失效（典型错误：`token_revoked`）。

## 错误语义（常见）
- `invalid_credential`：凭据错误。
- `password_not_set`：未设置密码但使用密码登录。
- `disabled`：账号被禁用。
- `locked`：失败次数触发临时锁定。
- `multiple`：身份定位歧义（需补班级或邮箱）。

## 相关文档
- `docs/how-to/student-login-and-submit.md`
- `docs/how-to/admin-manage-teachers-tui.md`
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/reference/permissions-and-security.md`

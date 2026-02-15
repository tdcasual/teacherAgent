# 权限与认证参考

- 适用角色：管理员、开发者
- 最后验证日期：2026-02-15

## 角色
- `student`: 学生角色，受 `student_id` 作用域约束。
- `teacher`: 教师角色，受 `teacher_id` 作用域约束。
- `admin`: 管理员角色，可执行账号管理与跨作用域管理操作。
- `service`: 服务角色，用于运维指标与内部任务。

## 认证模式
1. 学生/教师：identify + token/密码登录，成功后获取 Bearer token。
2. 管理员：
- 远程 API：`/auth/admin/login` 获取 Bearer token。
- 容器内：`admin_manager` trusted-local 模式直接管理（容器信任边界）。

## 关键安全机制
- token 与密码均以 hash 存储，不保存明文。
- 登录失败计数与锁定策略。
- token/password 重置后递增 `token_version`，旧 token 自动失效。
- 审计日志记录关键管理动作。

## 相关文档
- `docs/how-to/admin-manage-teachers-tui.md`
- `docs/how-to/auth-and-account-troubleshooting.md`
- `docs/http_api.md`

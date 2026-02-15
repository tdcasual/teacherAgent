# 账号与认证问题排查

- 适用角色：管理员、老师
- 前置条件：可访问 API 日志与容器
- 最后验证日期：2026-02-15

## 快速定位表
1. 无法登录（提示 `invalid_credential`）
- 核对账号定位信息（姓名/班级/邮箱）。
- 尝试管理员重置 token 或密码。

2. 提示 `disabled`
- 账号被禁用，管理员执行 `enable <teacher_id>` 或对应学生启用流程。

3. 提示 `token_revoked`
- 旧 token 已失效（通常因重置 token/密码导致 `token_version` 变化）。
- 重新登录获取新 access token。

4. 生产环境认证异常
- 检查 `AUTH_REQUIRED` 与 `AUTH_TOKEN_SECRET` 是否正确配置。

## 推荐排障顺序
1. 确认服务健康（`/health`）。
2. 确认账号状态（管理员列表查看 `is_disabled/password_set/token_version`）。
3. 必要时重置 token/密码。
4. 复测登录与核心业务路径。

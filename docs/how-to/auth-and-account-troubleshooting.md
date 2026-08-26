# 账号与认证问题排查

- 适用角色：管理员、老师
- 前置条件：可访问 API 日志与容器
- 最后验证日期：2026-08-26

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

## 已提交的 admin bootstrap 明文（必须轮换）

`data/auth/admin_bootstrap.txt` 曾被 git 跟踪，含明文 admin 密码。所有克隆/fork 仍持有该历史 blob，直到运营完成轮换。

**立即将该历史口令视为已泄露。** `.gitignore` 与取消跟踪只能阻止新提交，不能从 git 历史或既有克隆中抹去旧 blob。不要 rewrite `main` 历史，也不要把新密码提交进仓库。

生产/校内部署 **必须** 按顺序执行：

1. 轮换 admin 密码，停止使用历史 bootstrap 口令。
   - 可登录时：用 `POST /auth/admin/login` 确认仍能进入后立即改密。
   - 无法登录或没有改密接口时：设置新的 `ADMIN_PASSWORD` 环境变量，删除 volume 内 `admin_auth` 行与 `${DATA_DIR}/auth/admin_bootstrap.txt` 后重启 API（仅当确认无其他 admin）。引导流程会用新密码重建哈希，并把新明文只写到已被 gitignore 的 `DATA_DIR/auth/admin_bootstrap.txt`（`0600`）。
   - 容器内可用 `docker compose exec api admin_manager` 处置教师账号，但不能代替 admin 口令轮换。
2. **生产必做，不是提示**：同时轮换 `AUTH_TOKEN_SECRET` 以及 `AUTH_TOKEN_SECRET_FILE`（默认 `config/auth_token_secret`）的内容。旧 Bearer 全部失效，学生、教师、管理员必须重新登录。
3. GitHub secret scanning 对该历史明文应视为已泄露。

回滚注意：gitignore 规则不要回滚。口令与 `AUTH_TOKEN_SECRET` 轮换不可回滚到旧明文。

## 推荐排障顺序
1. 确认服务健康（`/health`）。
2. 确认账号状态（管理员列表查看 `is_disabled/password_set/token_version`）。
3. 必要时重置 token/密码。
4. 复测登录与核心业务路径。

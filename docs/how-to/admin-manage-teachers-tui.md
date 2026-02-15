# 管理员通过 TUI 管理教师账号

- 适用角色：管理员
- 前置条件：可进入 API 容器 shell
- 最后验证日期：2026-02-15

## 进入管理器
```bash
docker compose exec api admin_manager
```

## 常用命令
- `h`：查看帮助
- `f q 张老师`：按关键词过滤
- `sort tv desc`：按 token 版本倒序
- `sel add 1,3-5`：选择当前页中的行
- `batch disable`：批量禁用选中教师
- `batch reset auto`：批量重置密码并自动生成临时密码
- `r`：查看本次会话操作记录

## 单人操作
- `disable <teacher_id>`：禁用
- `enable <teacher_id>`：启用
- `reset <teacher_id> auto|manual`：重置密码

## 批量操作安全门
当批量影响人数 >5 时，系统要求输入确认词（例如 `DISABLE 12`），防止误操作。

## 验证结果
- 能看到教师列表。
- 执行禁用/启用后，状态与 `token_version` 有变化。
- 重置密码后，教师能使用新密码登录（或收到临时密码）。

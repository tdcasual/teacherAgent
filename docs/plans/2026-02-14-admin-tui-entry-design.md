# 2026-02-14 管理员 TUI 入口设计

## 目标
在不增加管理员前端页面的前提下，提供可在本机与 Docker 容器中直接运行的命令行交互入口，覆盖管理员管理教师账号的核心流程。

## 范围
- 交互登录：`POST /auth/admin/login`
- 教师管理：
  - `GET /auth/admin/teacher/list`
  - `POST /auth/admin/teacher/set-disabled`
  - `POST /auth/admin/teacher/reset-password`

## 方案选择
采用单文件脚本 `scripts/admin_auth_tui.py`：
- 标准库实现（`argparse` + `urllib` + `getpass`），避免新增依赖。
- 登录后进入菜单循环，按数字执行管理操作。
- 可通过 `--base-url` 指向 API（默认 `http://127.0.0.1:8000`）。

## 安全与运维
- 登录密码默认使用 `getpass` 隐藏输入。
- 自动生成临时密码时，仅在当前终端输出，避免写入日志文件。
- 支持在容器内执行：`docker compose exec api python3 /app/scripts/admin_auth_tui.py`。

## 验证
- `python3 -m ruff check scripts/admin_auth_tui.py`
- `python3 scripts/admin_auth_tui.py --help`


## Trusted-Local 模式（容器高信任）
- 新增 `admin_manager` 命令，默认携带 `--trusted-local`。
- trusted-local 模式下不再要求管理员用户名/密码登录，直接使用本地存储层执行教师管理操作。
- 审计仍记录为管理员操作（`actor_role=admin`），`actor_id` 使用当前管理员用户名（或 `ADMIN_USERNAME`）。
- 保留原 `admin_auth_tui.py` 的 API 登录模式，便于远程/非容器场景使用。

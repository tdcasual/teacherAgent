# 快速开始（5 分钟）

- 适用角色：老师、管理员
- 前置条件：已安装 Docker 与 Docker Compose
- 最后验证日期：2026-02-15

## 1. 启动服务
```bash
cp .env.production.min.example .env
# 先填 REDIS_PASSWORD / MCP_API_KEY / AUTH_TOKEN_SECRET / MASTER_KEY。这四项在 example 里为空；AUTH_TOKEN_SECRET 禁止 change_me
docker compose up -d
```

## 2. 访问入口
本机 loopback：
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`
- API：`http://localhost:8000`

校园局域网需要三件事一起改，只改 `PUBLISH_HOST` 不够：
```bash
# .env
PUBLISH_HOST=0.0.0.0
CORS_ORIGINS=http://<school-server>:3001,http://<school-server>:3002
VITE_API_URL=http://<school-server>:8000
docker compose build frontend_student frontend_teacher
docker compose up -d
```
校园客户端访问 `http://<school-server>:3002` / `:3001`，不要用老师电脑上的 localhost。

## 3. 管理员入口（容器高信任）
```bash
docker compose exec api admin_manager
```
说明：容器内 `admin_manager` 默认为 trusted-local 模式，不要求再次输入管理员账号密码。

## 4. 最小验证
1. 老师端可打开页面并发起一次请求。
2. 学生端可打开登录页。
3. `admin_manager` 能显示教师列表。

## 5. 常见问题
- API 不通：确认 `docker compose ps` 中 `api` 为 `healthy`。
- 管理命令不存在：重建镜像后重启 `api`。
```bash
docker compose build api
docker compose up -d api
```
- 本地非 Docker 调试 API：请使用 Python `3.13` 创建虚拟环境，保持与 CI / `pyproject.toml` 一致。
- GHCR 预构建前端 bake 的 `VITE_API_URL` 是 `http://127.0.0.1:8000`（见 `.github/workflows/docker.yml`）。校园局域网请按上面同时设置 `PUBLISH_HOST`、`CORS_ORIGINS`、`VITE_API_URL` 并重建前端镜像。

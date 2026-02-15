# 快速开始（5 分钟）

- 适用角色：老师、管理员
- 前置条件：已安装 Docker 与 Docker Compose
- 最后验证日期：2026-02-15

## 1. 启动服务
```bash
cp .env.production.min.example .env
docker compose up -d
```

## 2. 访问入口
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`
- API：`http://localhost:8000`

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

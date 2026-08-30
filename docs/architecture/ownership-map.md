# Ownership Map

本文档定义模块责任边界与默认评审人群组，避免“无人负责”与跨域误改。

## Ownership Matrix

| Module / Path | Primary Owner | Secondary Owner | Required Review For |
| --- | --- | --- | --- |
| `services/api/app.py` `services/api/container.py` | Platform/API | Runtime | 生命周期、依赖注入、启动/关闭流程 |
| `services/api/runtime/*` `services/api/workers/*` | Runtime | Platform/API | 线程模型、队列消费、关停行为 |
| `services/api/routes/chat_routes.py` `services/api/chat_*` `services/api/chat_job_processing/*` | Chat Domain | Runtime | chat 状态迁移、job 流程 |
| `services/api/routes/assignment_routes.py` `services/api/assignment/*` | Assignment Domain | Platform/API | assignment 编排、可见性策略、upload/confirm/progress |
| `packs/subjects/*` `services/api/subject_pack_service.py` | Assignment Domain | Platform/API | 学科 pack 装载；未知 id 回退 generic，永不回退物理 |
| `POST /auth/admin/assignments/{id}/claim` `services/api/assignment_meta_ownership_migrate_service.py` | Assignment Domain | Auth | 孤儿作业认领（admin only） |
| `frontend/apps/student/src/App.tsx` `frontend/apps/student/src/features/session/*` | Student Frontend | Platform/API | 会话壳层结构、跨模块状态 |
| `frontend/apps/student/src/features/chat/*` | Student Frontend | Chat Domain | 聊天渲染、发送/恢复交互 |
| `frontend/apps/student/src/features/workbench/*` | Student Frontend | Assignment Domain | 学习信息、侧栏信息架构 |
| `frontend/apps/teacher/src/App.tsx` `frontend/apps/teacher/src/features/layout/*` | Teacher Frontend | Platform/API | 应用壳层结构、跨模块状态 |
| `frontend/apps/teacher/src/features/chat/*` | Teacher Frontend | Chat Domain | 聊天渲染、发送/恢复交互 |
| `frontend/apps/teacher/src/features/workbench/*` | Teacher Frontend | Assignment Domain | 工作台、作业工作流（upload → confirm → progress） |
| `frontend/apps/teacher/src/features/settings/*` | Teacher Frontend | Platform/API | 模型与连接设置 |
| `frontend/vite.student.config.ts` `apps/shared/markdown.ts` | Frontend Platform | Student Frontend | 打包策略、bundle 预算 |
| `docs/architecture/*` | Platform/API | Frontend Platform | 边界规则、责任人定义 |

## Review Rules

1. 修改 `runtime` 或 `workers` 时，必须至少有 Runtime 角色评审。
2. 修改 `routes/*` 同时变更业务逻辑时，必须有对应 Domain 角色评审。
3. 修改 `App.tsx` 且新增 UI 区块时，必须确认是否可下沉至 `features/*`。教师端壳层改动应落在 `TeacherAppLayout`，而不是把 JSX 加回 `App.tsx`。
4. 变更 bundling 配置时，必须附带预算测试或构建产物对比证据。

## Escalation Guide

- 当单次 PR 同时涉及 3 个及以上 context（chat/assignment/frontend）时，需拆分为可独立回滚的提交。exam 域已移除，不要再把它当独立 context。
- 当边界冲突无法在当前 context 内解决时，优先新增 application 层适配，而不是跨层直接调用。

## Update Policy

- 新增目录或大模块时，必须在同一 PR 更新本文件。
- ownership 变更应同步更新 `docs/architecture/module-boundaries.md` 的变更清单与边界描述。

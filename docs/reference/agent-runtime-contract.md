# Agent Runtime Contract

本项目是一个教学 workflow 产品，不是通用 agent 平台。
运行时保留单一自然语言入口，但把老师、学生、管理员的主链路约束为可解释、可回归的固定流程。

## Runtime Chain

统一主链路如下：

`role -> workflow(skill) -> prompt stack -> tool policy -> chat job -> memory side effects -> history persistence`

### Step 1: `role`
- 老师：进入教学工作台与 teacher chat。
- 学生：进入作业陪练与学习对话。
- 管理员：进入账号、权限与运维管理链路。

### Step 2: `workflow(skill)`
- 运行时保留内部 `skill_id` 作为 workflow 标识，不把它暴露成“插件市场”。
- 老师端支持自动 workflow 解析：记录 `requested -> effective -> reason -> confidence -> candidates`。
- 显式指定 workflow 时优先使用显式选择；未指定时走角色默认或规则匹配。

### Step 3: `prompt stack`
- 基础系统提示由角色决定。
- workflow 运行时可追加更窄的教学上下文。
- 老师链路会在必要时注入教师上下文、考试上下文、作业上下文或附件文本上下文。

### Step 4: `tool policy`
- 工具集合先由角色决定，再由 workflow 进一步收紧。
- 高价值教学链路优先依赖显式前置校验与固定工具预算，不鼓励自由工具循环去“猜流程”。
- skill 级预算只能收紧全局预算，不能放宽。

### Step 5: `chat job`
- 每次请求都被包装成 chat job，并经过 `queued -> processing -> done|failed|cancelled` 状态机。
- 老师 job 会持久化 workflow 解析结果，并通过状态接口与 SSE 暴露轻量解释事件 `workflow.resolved`。
- SSE 主要承载排队、处理、工具调用、assistant 输出与 workflow 解释。

### Step 6: `memory side effects`
- 老师链路：先自动生成 memory proposal，再按会话触发 flush / compaction；默认不是直接写入长期记忆真值。
- 学生链路：根据对话与作业证据生成学生记忆提案。
- 管理员链路：以账号、权限、配置更新为主，不进入老师/学生记忆提案流程。

### Step 7: `history persistence`
- 老师端把 user / assistant turn 写入 teacher session，并更新 session index。
- 学生端把 user / assistant turn 写入 student session，并更新画像相关上下文。
- chat job 是执行与回放载体；history 是角色视角下的长期会话记录。

## Role Contracts

### Teacher
- 入口：teacher workbench。
- 目标：把考试分析、学生诊断、作业生成、课堂材料整理等高频动作收敛为可解释 workflow。
- 契约：允许自然语言输入，但高频链路要尽量走显式 workflow 解析与前置校验。

### Student
- 入口：student app。
- 目标：围绕“开始作业、学习陪练、错题讲解”维持稳定闭环。
- 契约：学生端不接收老师端 workflow 解释噪音；不允许误用 teacher-only workflow。

### Admin
- 入口：后台路由与管理工具。
- 目标：维护账号、权限、provider / model 配置与运维稳定性。
- 契约：管理员能力是产品运营链路，不扩展为独立 agent 平台。

## Built-in Workflows

| Workflow | `skill_id` | Primary Role | Typical Trigger |
| --- | --- | --- | --- |
| 考试分析 | `physics-teacher-ops` | Teacher | 考试分析、讲评、备课、教学运营 |
| 学生重点分析 | `physics-student-focus` | Teacher | 单个学生诊断、重点追踪、画像补充 |
| 作业生成 | `physics-homework-generator` | Teacher | 生成作业、分层练习、课后诊断 |
| 课堂材料采集 | `physics-lesson-capture` | Teacher | 板书 OCR、课堂图片整理、讲义草稿 |
| 学生陪练 | `physics-student-coach` | Student | 开始今天作业、错题讲解、学习陪练 |

## Product Boundaries

- 不做动态 skill marketplace。
- 不做通用多 agent 协作平台。
- 不把 tool loop 当作业务编排主入口。
- 优先保证老师 / 学生 / 管理员三条主链路可解释、可验证、可回归。

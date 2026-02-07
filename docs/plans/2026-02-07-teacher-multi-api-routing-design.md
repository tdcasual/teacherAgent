# Teacher Multi-API Routing Design (Mixed Tenant v1)

## Objective

在老师端实现“可自由配置多个 API 并自由选择模型”的能力，同时满足以下已确认约束：

- 租户模型：`混合`（机构共享 + 老师私有覆盖）
- 密钥策略：加密存储且不可回显
- 共享池权限：仅管理员维护，老师只读共享池
- 协议范围（v1）：仅 `OpenAI-Compatible`
- 模型选择：手动输入模型名，支持可选探测按钮
- 优先级：老师私有优先
- 失败回退：`fallback_channels -> 共享默认链`
- 密钥主密钥：`MASTER_KEY`；开发环境可默认值，生产环境必须显式配置
- 数据落盘：teacher workspace 下独立文件
- 生效方式：即时生效
- 生产 Base URL：仅允许 `https`

## Current State

当前系统已具备老师级路由基础能力：

- 老师可配置 `channel -> provider/mode/model` 并通过规则命中。
- 路由配置已按 teacher 维度隔离存储（`llm_routing.json`）。
- `model` 已支持自由输入。

当前主要缺口：

- `provider/mode` 来源是全局 registry，老师无法动态新增 provider。
- API Key/Base URL 依赖环境变量，缺少老师私有配置与密钥隔离。

## Solution Overview (Option B)

采用“共享 registry 只读 + 老师私有 registry 可写 + 运行时合并目录”的设计。

1. 共享目录继续使用全局 `config/model_registry.yaml`（管理员维护）。
2. 新增老师私有 provider 注册表（每个 teacher 独立文件）。
3. 运行时生成“有效 provider 目录”（共享 + 私有），冲突时私有优先。
4. 路由校验、仿真、实际调用均基于“有效目录”。
5. 路由提案/回滚机制保持不变，仅扩展其目录来源。

## Data Model

新增文件（每个老师）：

- `data/teacher_workspaces/<teacher_id>/provider_registry.json`
- `data/teacher_workspaces/<teacher_id>/provider_registry_audit.jsonl`

建议结构（`provider_registry.json`）：

```json
{
  "schema_version": 1,
  "updated_at": "2026-02-07T21:00:00",
  "updated_by": "teacher_xxx",
  "providers": [
    {
      "id": "tprv_main_proxy",
      "display_name": "Main Proxy",
      "type": "openai_compatible",
      "base_url": "https://proxy.example.com/v1",
      "api_key_encrypted": "ENC(...)",
      "api_key_masked": "sk-****abcd",
      "default_mode": "openai-chat",
      "default_model": "gpt-4.1-mini",
      "enabled": true,
      "created_at": "2026-02-07T20:00:00",
      "updated_at": "2026-02-07T21:00:00"
    }
  ]
}
```

说明：

- `id` 为系统唯一标识，建议前缀 `tprv_`，避免与共享 provider 命名冲突。
- `api_key_encrypted` 仅用于服务端解密调用，不对外返回。
- `api_key_masked` 用于 UI 展示。

## Security Design

### Key Encryption

- 使用 `MASTER_KEY` 进行认证加密（如 AES-GCM）。
- API 不提供明文回显；更新 key 采用 rotate 语义。

### MASTER_KEY Policy

- 非生产环境：若未配置 `MASTER_KEY`，允许使用开发默认值，并输出高优先级告警日志。
- 生产环境：若未配置 `MASTER_KEY`，服务启动失败。

### Base URL Policy

- 生产环境仅允许 `https://`。
- 开发环境可按配置允许 `http://`（默认建议仍为 `https://`）。
- 统一做 URL 规范化（去尾 `/`、最小合法性校验）。

## API Design (v1)

新增老师私有 provider 管理接口：

1. `GET /teacher/provider-registry`
- 返回：私有 provider（脱敏）+ 共享 provider（只读）+ 合并目录。

2. `POST /teacher/provider-registry/providers`
- 创建私有 provider。
- 输入：`display_name/base_url/api_key/default_model/enabled`。

3. `PATCH /teacher/provider-registry/providers/{provider_id}`
- 更新元信息；若传 `api_key` 则视为 rotate。

4. `DELETE /teacher/provider-registry/providers/{provider_id}`
- v1 建议软删除（或禁用），保留审计链路。

5. `POST /teacher/provider-registry/providers/{provider_id}/probe-models`（可选）
- 基于该 provider 探测模型列表；失败不阻塞手填模型。

## Frontend Design (Teacher)

新增“Provider 管理”页（或在路由页增加管理面板）：

- 列表展示共享 provider（只读）与私有 provider（可编辑）。
- 新增/编辑私有 provider 时可自定义 `base_url`（用于中转）。
- API Key 输入后仅显示掩码，不支持回显。

路由页面改造：

- `provider` 下拉使用“合并目录”。
- `model` 继续保留自由输入。
- 可选“探测模型”按钮，仅辅助，不强依赖。

## Runtime Routing and Fallback

路由优先级按既定策略：

1. 命中规则得到首个 channel。
2. 先按 `fallback_channels` 形成候选链。
3. 对每个候选 channel 尝试调用（私有 provider 优先）。
4. 候选链全部失败后，走共享 `fallback_chain`。

`agent` 维度兼容约束（与现有聊天链路对齐）：

- 聊天 `kind` 可能为 `chat.agent.<agent_id>`（例如 `chat.agent.opencode`），路由规则必须支持该模式。
- 建议在老师路由规则中同时保留：
  - 通用规则：`chat.agent`
  - agent 专属规则：`chat.agent.opencode`（或其他 agent 后缀）
- agent 专属规则优先级应高于通用规则，避免误命中。

失败分类：

- `401/403`：密钥或权限错误（配置错误）。
- `404`：中转或 endpoint 不兼容。
- `429/5xx/timeout`：可重试/可回退错误。

## Validation Rules

新增/扩展校验：

- 私有 provider `id`、`base_url`、`default_model` 的格式校验。
- 生产环境 `base_url` 必须为 `https`。
- 路由配置校验改为依据“合并目录”判断 `provider/mode` 合法性。
- channel 若引用已禁用 provider，校验给出错误或强告警（按接口语义区分）。
- 当请求处于“自动 skill 路由”模式时，`skill_id` 可能为空；provider 路由不得依赖 `skill_id` 必填，应优先依据 `role/kind/capabilities` 决策。

## Skill Routing Integration Notes

为了避免“老师通过聊天配置模型路由”场景误匹配，建议同步更新 `physics-llm-routing` 的 `routing` 关键词，增加以下词项：

- `api key`
- `base url`
- `中转`
- `代理地址`
- `provider registry`
- `私有 provider`

并为其中高信号词（如 `base url`、`中转`、`私有 provider`）配置更高权重。

## Testing Strategy

测试分层：

1. 单元测试
- 加解密、掩码、`MASTER_KEY` 门禁。
- 私有 provider CRUD 与审计写入。
- 合并目录（私有覆盖共享）。

2. 路由测试
- 校验/仿真读取合并目录。
- 私有 provider 调用失败后正确回退。

3. API 集成测试
- 新增 provider 接口全流程。
- 老师隔离：A 老师不可读取 B 老师私有 provider。
- 回归：现有 `/teacher/llm-routing*` 行为不退化。

## Rollout Plan

分三阶段灰度：

1. 后端私有 registry + 加密存储 + 管理 API。
2. 运行时合并目录 + 调用链支持私有 provider。
3. 老师端 UI 开放 provider 管理与路由联动。

每阶段均以回归测试通过为闸门，支持快速回滚到“仅共享 registry”模式。

## Implementation Task Breakdown

### Phase 1: Backend Storage and Security

1. 新增 `teacher_provider_registry_service.py`（读写、原子落盘、审计日志）。
2. 新增加密模块（`MASTER_KEY` 加载、加解密、掩码逻辑）。
3. 增加环境门禁：`ENV=production` 且无 `MASTER_KEY` 时启动失败。
4. 增加 `base_url` 生产环境 `https` 校验。

### Phase 2: Provider APIs

1. 新增 API models：
   - create/update/list/delete/probe 请求与响应 DTO
2. 新增路由：
   - `GET /teacher/provider-registry`
   - `POST /teacher/provider-registry/providers`
   - `PATCH /teacher/provider-registry/providers/{provider_id}`
   - `DELETE /teacher/provider-registry/providers/{provider_id}`
   - `POST /teacher/provider-registry/providers/{provider_id}/probe-models`
3. 严格返回脱敏字段，禁止明文 key 回显。

### Phase 3: Runtime Merge and Resolve

1. 实现共享+私有 provider 目录合并（私有优先）。
2. `teacher_llm_routing` 目录来源切换到“合并目录”。
3. `chat_runtime` 调用命中私有 provider 时，使用私有 `base_url/api_key` 构造 target。
4. 保持 fallback 顺序：`fallback_channels -> shared fallback_chain`。
5. 确保规则支持 `chat.agent.<agent_id>` 类型。

### Phase 4: Teacher Frontend

1. 新增 provider 管理视图（增删改启停、key rotate、掩码显示）。
2. 路由页面 `provider` 下拉接入合并目录。
3. `model` 保持自由输入；增加“探测模型”按钮（失败不阻断）。
4. 在提示文案中明确自动 skill 路由场景下 `skill_id` 可为空。

### Phase 5: Test Matrix

1. 单元测试：加解密、掩码、`MASTER_KEY` 门禁、URL 校验。
2. API 测试：provider CRUD、脱敏返回、老师隔离。
3. 路由测试：合并目录校验、agent kind 命中、私有失败回退共享。
4. 回归测试：现有 `/teacher/llm-routing*`、`chat.start/status`、前端 e2e 不退化。

## Out of Scope (v1)

- 非 OpenAI-Compatible 协议（如 Gemini Native 自定义适配）。
- 共享池写入与审批流。
- KMS 托管主密钥。
- provider 级细粒度限流/配额计费看板。

## Done Definition

- 老师可新增多个私有 API（自定义 `base_url`、key 加密存储、即时生效）。
- 老师路由页面可选择“共享 + 私有”provider，并自由填写 model。
- 运行时按“私有优先 + 既定回退策略”稳定执行。
- 生产环境 `https` 约束与 `MASTER_KEY` 强约束生效。
- 自动化测试覆盖关键路径并通过。

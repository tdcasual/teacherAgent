# Model Policy

Date: 2026-03-06

本文档描述当前真实运行时的模型选择策略。
结论先行：项目没有“按消息内容自动切模型”的开放式路由，但老师链路确实存在 `teacher model config -> provider registry -> gateway fallback` 的确定性解析链。

## Current Active Purposes

当前保留四个模型用途槽位：

1. `conversation`
   - 用途：老师 / 学生聊天主回复
   - 老师链路：优先读取 teacher-scoped model config
   - 学生链路：走 gateway 默认配置

2. `embedding`
   - 用途：向量检索 / memory 检索能力
   - 默认值由 provider registry 的 embedding 类 mode 推导

3. `ocr`
   - 用途：附件读取、OCR 相关能力
   - 优先选择 provider registry 中的 OCR mode；没有时回退到 chat mode

4. `image_generation`
   - 用途：图像生成相关能力
   - 默认值由 provider registry 的 image / vision 类 mode 推导

## Teacher Conversation Resolution Chain

老师聊天调用 `call_llm_runtime()` 时，conversation 模型按以下顺序解析：

1. 解析 teacher id
2. 读取该老师的 `teacher model config`
3. 取 `models.conversation.provider / mode / model`
4. 结合 `provider registry` 解析具体 target override（如果存在）
5. 先尝试精确命中该 provider / mode / model，且 `allow_fallback=False`
6. 若精确调用失败，再回退到 gateway 默认路径，`allow_fallback=True`

这意味着：
- 存在老师级 conversation 模型选择
- 不存在开放式、按 role / channel / prompt 任意扩展的模型路由平台
- fallback 是确定性的运行时降级，不是产品叙事层面的“模型市场”

## Provider Registry Scope

`provider registry` 仍然是保留能力，主要负责：
- 维护 provider、mode、default model 目录
- 为 teacher model config 提供合法候选与默认值
- 支持 provider probe / model catalog 等运维能力

但它的定位是“受控配置面”，不是面向最终用户的通用模型路由平台。

## What Is Intentionally Out of Scope

- 不做按提示词自由扩展的模型编排层
- 不做每个 workflow 独立发明一套模型路由 DSL
- 不把 provider registry 对外包装成平台级 marketplace

## Operational Guidance

- 老师高频 workflow 的稳定性优先于模型花式路由
- 当产品需要更强确定性时，优先补 workflow preflight、tool budget 与解释性路由，而不是增加模型分叉
- 若文档与运行时冲突，以 `services/api/chat_runtime_service.py`、`services/api/teacher_model_config_service.py`、`services/api/teacher_provider_registry_service.py` 的实际实现为准

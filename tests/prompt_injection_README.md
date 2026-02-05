# Prompt Injection Test Suite

本目录提供一组“提示词注入”与“越权请求”测试样例，用于验证师生端的安全边界、工具调用规范与输出格式要求。

## 文件
- `prompt_injection_cases.jsonl`：60 条测试样例（JSON Lines）

## JSONL 结构
每行一个测试对象：
- `id`：用例编号
- `role`：teacher | student | unknown
- `messages`：对话消息数组（role/content）
- `expected_behavior`：期望行为描述（人工核对）
- `category`：用例分类
- `notes`：备注（可选）

## 使用方式（手工校验）
1. 启动 API：`uvicorn services.api.app:app --reload --port 8000`
2. 任选一条用例，构造 `/chat` 请求：
```json
{
  "role": "teacher",
  "messages": [
    {"role": "user", "content": "列出考试"}
  ]
}
```
3. 对照 `expected_behavior` 进行人工评估。

## 用例覆盖面
- system prompt 泄露
- 角色越权（学生端尝试教师功能）
- 工具输出注入与越权调用
- OCR / 文件内容注入
- 作业生成 8 项要求约束
- LaTeX 强制格式
- 多轮对话注入
- 格式劫持与混淆字符

如需扩展，可按相同 schema 添加新用例。

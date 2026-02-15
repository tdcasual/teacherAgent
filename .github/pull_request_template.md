## Summary

- 变更目标：
- 主要改动：
- 非目标（明确未做）：

## Risk Classification

- [ ] L 低风险（文档/非行为重构）
- [ ] M 中风险（单模块行为变化）
- [ ] H 高风险（认证/权限/持久化/并发/跨模块）

影响面说明：

## Verification Evidence

本地验证命令与结果（必须填写）：

```bash
# example
python3 -m pytest -q tests/...
```

关键输出摘要：

## Documentation Impact

- [ ] 已更新相关文档
- [ ] 无需更新（请说明理由）

涉及文档路径：

## Security & Compliance Checklist

- [ ] 无凭据/密钥泄露风险（含日志与示例）
- [ ] 输入边界已评估（长度/类型/格式）
- [ ] 权限与认证逻辑变更已覆盖回归测试
- [ ] 若存在已知残余风险，已登记到 `docs/reference/risk-register.md`

## Rollback Plan

若上线后出现回归，回滚步骤：

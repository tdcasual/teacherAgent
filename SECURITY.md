# Security Policy

本文件定义漏洞报告与安全变更治理流程。

## 报告安全漏洞

请不要在公开 issue 中披露可利用细节。

请通过 GitHub Security Advisory 私下报告：打开仓库的 **Security → Advisories → New advisory**，或访问

https://github.com/tdcasual/teacherAgent/security/advisories/new

并创建 private advisory。不要使用公开 issue。若无法打开 Advisory 页面，请开一个不含利用细节的 issue，请求维护者开启 private advisory。

报告建议包含：

1. 影响范围（模块/接口/角色）。
2. 复现步骤（最小 PoC）。
3. 预期风险等级（低/中/高）。
4. 可能缓解方案（可选）。

## 响应目标

1. 24 小时内确认已收到报告。
2. 72 小时内给出初步分级与处置计划。
3. 高风险问题优先修复并安排补丁发布。

## 支持范围

当前优先支持 `main` 分支。  
历史分支是否回补由维护者按影响面与成本评估决定。

## 安全基线要求

1. 凭据与密钥不得硬编码到仓库。
2. 认证与权限变更必须带回归测试与审计验证。
3. 用户输入必须有大小/类型/格式边界。
4. 发现可疑行为必须可追溯到审计日志。

## 合规与风险接受

1. 对暂不修复但可接受的风险，必须登记到：
   `docs/reference/risk-register.md`
2. 风险条目需包含：
   - 风险描述
   - 补偿控制
   - Owner
   - 复审日期
   - 退出条件

## 历史凭据作废

`data/auth/admin_bootstrap.txt` 曾被提交到 git，含明文管理员口令。该历史口令 **已作废**，必须视为已泄露。

Git 历史与既有克隆/fork 仍可能持有旧 blob。Owner 已决：不 rewrite `main` 历史、不做 `git filter-repo`。取消跟踪与 gitignore 只能阻止新提交。

生产/校内部署 **必须** 同时：

1. 轮换 admin 密码，停止使用历史 bootstrap 口令。
2. 轮换 `AUTH_TOKEN_SECRET`（及 `AUTH_TOKEN_SECRET_FILE` 内容）。旧 Bearer 全部失效，所有角色必须重新登录。

操作步骤见 `docs/how-to/auth-and-account-troubleshooting.md`。不要把新明文提交进仓库。

## 安全变更发布

1. 高风险修复合并前需至少 2 名评审。
2. 合并后必须观察 CI 与关键运行指标。
3. 若出现回归，按回滚策略优先恢复系统稳定性。

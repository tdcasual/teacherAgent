# Teacher Scroll Isolation Design

## Background

桌面端老师页面在长会话场景下存在滚动链外溢问题：聊天区滚轮触顶/触底后，页面级滚动被触发，导致左侧历史会话与右侧工作台整体位移，影响持续使用。

## Goal

在桌面端实现严格滚动隔离：

1. 页面级滚动锁定。
2. 聊天区、历史区、工作台各自独立滚动。
3. 滚动链不向外层传播，避免“连带滚动”。

## Design

### 1) Root Scroll Lock (Desktop)

- 在桌面断点下锁定 `html/body/#root` 的滚动。
- 老师端根容器 `.app.teacher` 使用固定视口高度，并禁用溢出。

### 2) Panel-only Scrolling

- `teacher-layout` 明确为非滚动容器（`overflow: hidden`）。
- 三个滚动容器保持唯一职责：
  - 聊天：`.messages`
  - 历史：`.session-groups`
  - 工作台：`.skills-body` / `.workbench-memory`

### 3) Overscroll Chain Blocking

- 对上述三个滚动容器设置 `overscroll-behavior: contain`，阻断向父层传播。
- 顶层容器设置 `overscroll-behavior: none`，避免页面链路参与。

## Verification

新增 Playwright 回归用例：

- `desktop enforces isolated scroll contract`
  - 断言 `.app.teacher` 与 `body` 在桌面端为 `overflow: hidden`。
  - 断言 `.messages`、`.session-groups`、`.skills-body` 的 `overscroll-behavior-y` 为 `contain`。

同时执行现有老师端 E2E 全量回归，确保召唤协议、自动路由、滚动行为不回归。

## Result

桌面端滚动职责已收敛为“面板内滚动”，长会话不会再挤占历史区与工作台可用性。

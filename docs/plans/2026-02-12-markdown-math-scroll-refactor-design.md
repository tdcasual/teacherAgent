# Markdown / 数学公式渲染 & 学生端 UI 滚动全面重构

> 日期: 2026-02-12
> 范围: 学生端为主，教师端参考迁移
> 目标设备: 桌面 + 移动端

---

## 1. 数学公式渲染修复

### 问题
- KaTeX display math 和长行内公式无溢出处理，撑破 `.bubble` 容器
- `.text` 的 `overflow-wrap: anywhere` 对 KaTeX 绝对定位元素无效
- 公式解析失败时的红色错误文本不够友好

### 方案

**CSS 溢出守卫** (`styles.css`):
```css
.markdown .katex-display {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
}
.markdown .katex {
  overflow-wrap: normal;  /* 覆盖父级 anywhere，避免 KaTeX 内部断行错位 */
}
```

移动端 ≤900px 追加:
```css
.markdown .katex-display {
  -webkit-overflow-scrolling: touch;
}
```

**Sanitize 验证**: 确认 `katexSchema` 允许 `math` / `math-display` class 通过。

**错误降级样式**:
```css
.katex-error {
  background: #f3f4f6;
  font-family: monospace;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  color: #6b7280;
}
```

---

## 2. 滚轮隔离系统（共享化）

### 问题
- 教师端有 `useWheelScrollZone`（3 区域），学生端完全无滚轮隔离
- 教师端实现有已知缺陷：`isMobileViewport()` 非响应式、`preventDefault` 过于激进

### 方案

**创建** `frontend/apps/shared/useWheelScrollZone.ts`:
- 泛型区域支持：`useWheelScrollZone<Zone extends string>(config)`
- 学生端传入 `zones: ['chat', 'sidebar']`，教师端保留 `['chat', 'session', 'workbench']`
- `resolveTarget(zone)` 由调用方提供，映射区域名到 DOM 元素
- 修复响应式检测：`matchMedia('(max-width: 900px)')` 监听 `change` 事件
- 添加 `passive` 能力检测
- 移动端完全禁用（依赖原生触摸滚动）

**学生端集成** (`App.tsx`):
- 区域映射：`'sidebar'` → `.session-sidebar`，`'chat'` → `.messages`
- 侧边栏关闭时重置到 `'chat'`

**教师端迁移**: 将 `useWheelScrollZone.ts` 改为从 shared 导入，保持现有配置。

---

## 3. 智能自动滚动

### 问题
- `scrollIntoView` 在每次 `messages` 变化时触发，包括加载历史消息
- 用户回看历史时被强制拉回底部
- `markdownCacheRef` 无上限，长会话内存泄漏

### 方案

**创建** `frontend/apps/shared/useSmartAutoScroll.ts`:
```ts
interface UseSmartAutoScrollReturn {
  messagesRef: RefObject<HTMLDivElement>;
  endRef: RefObject<HTMLDivElement>;
  isNearBottom: boolean;
  scrollToBottom: () => void;
}
```
- 监听 `.messages` 的 `scroll` 事件，距底部 < 80px 时 `isNearBottom = true`
- 只在 `isNearBottom === true` 时自动滚动
- 暴露 `scrollToBottom()` 供手动调用

**"新消息"浮标**:
- 当 `!isNearBottom && hasNewMessage` 时，在聊天区底部显示 "↓ 新消息" 浮标
- 点击调用 `scrollToBottom()`
- CSS fade-in/out 动画，不遮挡 composer

**历史消息加载保位**:
- prepend 旧消息前记录 `scrollHeight`
- 插入后恢复 `scrollTop += newScrollHeight - oldScrollHeight`

**Markdown 缓存 LRU**:
- `markdownCacheRef` 限制 500 条
- 超出时删除最早插入的条目（Map 保持插入顺序）

---

## 4. Markdown 排版优化 + 移动端适配

### 问题
- GFM 表格无样式，可能溢出容器
- 移动端 ≤900px 存在双重滚动（页面级 + `.messages` 容器）
- 图片无 `max-width` 约束
- 代码块字体偏大

### 方案

**表格溢出守卫** (`styles.css`):
```css
.markdown table {
  display: block;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 0 0 6px;
  font-size: 14px;
}
.markdown th, .markdown td {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}
.markdown tr:nth-child(even) {
  background: #f9fafb;
}
```

**代码块微调**:
```css
.markdown pre code {
  font-size: 13px;
  line-height: 1.5;
}
```
暂不引入语法高亮库，保持轻量。

**移动端双重滚动修复**:
```css
@media (max-width: 900px) {
  html, body, #root {
    overflow: hidden;
    height: 100dvh;
  }
  .messages {
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
  }
}
```

**图片自适应**:
```css
.markdown img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
```

---

## 5. 文件变更清单

### 新建文件
| 文件 | 说明 |
|------|------|
| `frontend/apps/shared/useWheelScrollZone.ts` | 通用滚轮隔离 hook |
| `frontend/apps/shared/useSmartAutoScroll.ts` | 智能自动滚动 hook |
| `frontend/e2e/student-markdown-math-scroll.spec.ts` | E2E 测试 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `frontend/apps/student/src/styles.css` | KaTeX 溢出守卫、表格样式、移动端修复、图片自适应 |
| `frontend/apps/student/src/App.tsx` | 集成 useSmartAutoScroll、useWheelScrollZone、LRU 缓存 |
| `frontend/apps/student/src/features/chat/StudentChatPanel.tsx` | 添加"新消息"浮标组件 |
| `frontend/apps/shared/markdown.ts` | 验证 sanitize schema（可能无需改动） |
| `frontend/apps/teacher/src/features/chat/useWheelScrollZone.ts` | 迁移为从 shared 导入 |

---

## 6. 实施顺序

1. **CSS 修复**（KaTeX 溢出、表格、图片、移动端双重滚动）— 纯样式，零风险
2. **useSmartAutoScroll** hook 创建 + 学生端集成 — 替换现有 scrollIntoView
3. **Markdown 缓存 LRU** — App.tsx 中 markdownCacheRef 改造
4. **useWheelScrollZone 共享化** — 提取到 shared + 学生端集成
5. **教师端迁移** — useWheelScrollZone 改为从 shared 导入
6. **"新消息"浮标** UI — StudentChatPanel 新增组件
7. **E2E 测试** — 覆盖公式溢出、智能滚动、移动端

---

## 7. 风险与注意事项

- **滚轮隔离的 trackpad 体验**: 手动 `scrollTop += deltaY` 会丢失惯性滚动。可考虑在共享 hook 中添加简单的动量模拟，但优先级低。
- **KaTeX sanitize**: rehype-sanitize 可能过滤掉 KaTeX 需要的某些属性。修改后需用包含复杂公式的消息做回归测试。
- **教师端迁移**: 共享化 useWheelScrollZone 时需确保教师端的三区域逻辑不受影响，建议先写测试再迁移。
- **移动端 `overflow: hidden`**: 在 ≤900px 下锁定页面滚动可能影响某些浏览器的地址栏自动隐藏行为，需在 iOS Safari 上实测。

# 2026-05-07 智能助手快捷访问图标

## 需求描述

在应用界面中添加一个浮动快捷图标（类似 FloatButton），用户随时可以点击该图标打开一个小型快速聊天窗口，无需导航到 `/smart-assistant` 页面即可与智能助手对话。

## 现状分析

1. **已有智能助手**：`SmartChatPage.jsx` 在 `src/features/smart-assistant/pages/` 中，支持 SSE 流式对话、会话管理、工具结果展示
2. **已有浮动聊天组件**：`ChatInterface.jsx` 在 `src/shared/components/` 中，使用 Ant Design FloatButton + Popover，但**未被任何页面使用**，且支持多种后端（DeepSeek/Ollama/Ragflow/Dify），不是智能助手专用
3. **API 层**：`smartAssistantApi.js` 提供 `sendSmartChatStream`（SSE 流式）、`getSessions`、`createSession`、`deleteSession` 等方法
4. **布局结构**：`App.js` 中是 Sidebar + main-content（包含 Outlet），所有带 sidebar 的页面都通过这个 layout 渲染

## 方案设计

### 整体思路

创建一个新的浮动组件 `QuickAssistant`，放在 `App.js` 的主布局中，全局可见。点击 FloatButton 弹出一个小型聊天面板，复用智能助手的 API 和部分 UI 组件。

### 需要新建的文件

| 文件 | 说明 |
|------|------|
| `src/shared/components/QuickAssistant.jsx` | 浮动快捷助手主组件（FloatButton + Popover/Modal 聊天面板） |
| `src/shared/components/QuickAssistant.css` | 浮动助手样式 |

### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `src/App.js` | 在 App layout 中添加 `QuickAssistant` 组件（与 Sidebar + Outlet 同级） |

## 实施细节

### QuickAssistant 组件

```
QuickAssistant (shared/components/QuickAssistant.jsx)
├── FloatButton (右下角，RobotOutlined，tooltip: "智能助手")
├── 点击后展开小型聊天面板 (~400x500px)
│   ├── Header: "智能助手" + 最小化/关闭按钮
│   ├── 消息列表区域 (复用 SmartChatPage 的消息渲染逻辑)
│   │   ├── 用户消息气泡
│   │   ├── 助手消息气泡
│   │   └── ToolResult 组件（复用 smart-assistant/components/ToolResult）
│   ├── 输入区域
│   │   ├── TextArea 输入框
│   │   └── 发送按钮
│   └── 底部：可选 "打开完整页面" 链接 → 导航到 /smart-assistant
└── 状态管理
    ├── messages 列表
    ├── currentSessionId
    ├── loading / streaming 状态
    └── 使用 smartAssistantApi 的 API
```

### 核心逻辑

1. **会话管理**：首次打开时自动 `createSession`，后续复用同一会话
2. **消息发送**：调用 `sendSmartChatStream` 实现流式响应
3. **面板交互**：
   - 点击 FloatButton 打开/关闭面板
   - 面板内支持最小化（收起为 FloatButton）和关闭
4. **样式**：
   - 固定定位，右下角，z-index 高于 sidebar
   - 面板尺寸约 400x500px（移动端全屏）
   - 复用 SmartChatPage 的消息气泡样式（或引用其 CSS）

### 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 面板容器 | Ant Design Drawer | Drawer 从侧边滑出，适合快速聊天窗口，比 Modal 更轻量自然 |
| 状态管理 | 组件内 useState | 简单场景无需 Redux/Zustand，符合项目当前模式 |
| 消息渲染 | 复用 SmartChatPage 的渲染逻辑 | 避免重复代码，保持一致性 |
| 拖拽功能 | 暂不实现 | MVP 先实现核心功能，拖拽可后续添加 |

## 实施步骤

### Phase 1: 创建 QuickAssistant 组件

- [ ] 创建 `src/shared/components/QuickAssistant.jsx`
  - FloatButton 触发器
  - Drawer 聊天面板
  - Header（标题 + 关闭按钮 + 跳转完整页面链接）
  - 消息列表渲染（复用 SmartChatPage 的消息展示逻辑）
  - 输入框 + 发送按钮
- [ ] 创建 `src/shared/components/QuickAssistant.css`
  - 面板布局样式
  - 消息气泡样式（可引用/复用 SmartChatPage.css 的样式类）
  - 输入区域样式

### Phase 2: 集成聊天逻辑

- [ ] 接入 `smartAssistantApi.js` 的 API
  - createSession（首次打开时）
  - sendSmartChatStream（消息发送，SSE 流式）
  - 处理流式响应，更新消息状态
- [ ] 集成 `ToolResult` 组件渲染工具结果
- [ ] 处理加载/流式状态指示器

### Phase 3: 全局挂载

- [ ] 修改 `src/App.js`，在 layout 中添加 `<QuickAssistant />`
- [ ] 验证在所有带 Sidebar 的页面中均可使用
- [ ] 验证移动端响应式表现

### Phase 4: 测试与优化

- [ ] 手动测试快捷图标的打开/关闭
- [ ] 测试消息发送和流式响应
- [ ] 测试会话创建和复用
- [ ] 测试 "打开完整页面" 跳转
- [ ] 检查 z-index 层级冲突
- [ ] 检查移动端适配

## 风险评估

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| SSE 流式在 Drawer 中渲染异常 | MEDIUM | 复用 SmartChatPage 已验证的流式处理逻辑 |
| z-index 与 Sidebar/Popover 冲突 | LOW | 使用 Ant Design Drawer 的默认 z-index（通常高于 sidebar） |
| 面板内容在小屏幕溢出 | MEDIUM | 添加响应式样式，小屏幕使用全屏模式 |
| 会话状态丢失（页面刷新） | LOW | MVP 不处理，后续可加 localStorage 缓存 |

## 预计复杂度: LOW

- 前端组件开发: 2-3 小时
- 测试与调试: 1 小时
- 总计: 3-4 小时

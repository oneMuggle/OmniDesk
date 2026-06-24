# AI 能力演示模式 — 设计规范

**日期：** 2026-06-24
**项目：** OmniDesk
**作者：** Claude
**状态：** 待用户审阅

## 1. 背景与目标

### 1.1 问题
OmniDesk 已在后端建立 Dify 与 RAGFlow 接入能力（`dify_apps`、`ragflow_service` 两个 Django app），前端也已实现管理界面（`DifyAppManagementPage`、`DifyAppViewer`、`RagflowChatPage`）和路由（`/dify-apps`、`/dify-apps/:appId`、`/ragflow-chat`）。

但实际生产环境的 Dify / RAGFlow 服务尚未部署：

- `DifyApp.embed_url` 为占位符，iframe 加载失败
- `RagflowConfig.query()` 转发到真实 RAGFlow API 时连接超时
- 直接向客户/领导演示时，所有 AI 相关页面都报红

### 1.2 目标
让现有 AI 接入页面在**没有真实后端服务**时仍能完整跑通核心流程，并新增一个集中的"AI 能力展示"入口页，方便对外演示。

### 1.3 非目标
- 不实际部署 Dify 或 RAGFlow 服务
- 不改变现有 UI 组件的代码逻辑（仅通过 axios 拦截器附加 demo 行为）
- 不修改后端 API（mock 完全在前端）
- 不引入 MSW 等重量级 mock 框架

## 2. 设计方案

### 2.1 架构

```
┌──────────────────────────────────────────────────┐
│  Layout 顶部  ◯ 演示模式 [●━━○]                 │  DemoToggle
└────────────┬─────────────────────────────────────┘
             │ (Context: DemoContext, localStorage 持久化)
             ▼
┌──────────────────────────────────────────────────┐
│ Axios Interceptor (axiosConfig.js)              │
│   ├─ toggle ON  →  URL 模式匹配 → 返回 mock    │
│   └─ toggle OFF →  放行到真实后端               │
└────────────┬─────────────────────────────────────┘
             ▼
┌──────────────────┬───────────────────────────────┐
│ /ai-showcase     │ /dify-apps  /dify-apps/:id    │
│ 入口页           │ /ragflow-chat                 │
│ Dify 卡片 +      │ 现有页面，demo 模式下自动跑通 │
│ RAGFlow 卡片     │                               │
└──────────────────┴───────────────────────────────┘
```

### 2.2 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| Mock 位置 | 仅前端 axios 拦截器 | 不污染业务代码、不动后端 |
| 启用机制 | 运行时 toggle + localStorage 持久化 | 演示中可即时切换，刷新保留偏好 |
| 内容来源 | Dify 官方 demo URL + 前端预置问答表 | 真实可点的 demo，无需后端 |
| 入口页 | 新增 `/ai-showcase` | 提供集中入口，避免侧边栏分散 |

## 3. 组件与文件清单

### 3.1 新增文件

| 路径 | 用途 |
|---|---|
| `omni_desk_frontend/src/shared/context/DemoContext.jsx` | 全局 demo 开关状态，默认 `false`，localStorage key `omnidesk:demo-mode` |
| `omni_desk_frontend/src/shared/components/DemoToggle.jsx` | 顶部 toggle 组件（Ant Design Switch） |
| `omni_desk_frontend/src/shared/api/demoMocks.js` | mock 数据：3 个 Dify 应用 + 2 个 RAGFlow 配置 + 问答响应表 |
| `omni_desk_frontend/src/shared/api/demoInterceptor.js` | axios 请求拦截器，URL 模式匹配后返回 mock 响应 |
| `omni_desk_frontend/src/shared/pages/AIShowcasePage.jsx` | 新增 `/ai-showcase` 入口页 |
| `omni_desk_frontend/src/shared/pages/AIShowcasePage.css` | 样式 |
| `omni_desk_frontend/src/shared/pages/__tests__/AIShowcasePage.test.jsx` | 组件测试 |
| `omni_desk_frontend/src/shared/api/__tests__/demoInterceptor.test.js` | 拦截器单元测试 |

### 3.2 修改文件（最小改动）

| 路径 | 改动 |
|---|---|
| `omni_desk_frontend/src/shared/api/axiosConfig.js` | 注册 `demoInterceptor`（仅 1 行） |
| `omni_desk_frontend/src/shared/components/Layout.jsx` | 嵌入 `<DemoToggle />`（顶部右侧） |
| `omni_desk_frontend/src/routes/index.jsx` | 注册 `/ai-showcase` 路由 |
| `omni_desk_frontend/src/shared/config/menuConfig.jsx` | 侧边栏加 "AI 能力展示" 菜单项 |

## 4. 数据契约

### 4.1 Mock 数据

```javascript
// demoMocks.js（精简示意）
export const MOCK_DIFY_APPS = [
  { id: 1, name: '智能客服助手', description: '面向客户的 7×24 智能问答机器人',
    embed_url: 'https://udify.app/chatbot/<官方demo-id>',
    is_active: true, created_at: '...', updated_at: '...' },
  { id: 2, name: '合同审查助手', description: '法务合同要点提取与风险标注',
    embed_url: 'https://udify.app/chatbot/<官方demo-id>',
    is_active: true, ... },
  { id: 3, name: '员工手册问答', description: 'HR 政策智能检索',
    embed_url: 'https://udify.app/chatbot/<官方demo-id>',
    is_active: false, ... },
];

export const MOCK_RAGFLOW_CONFIGS = [
  { id: 1, name: '企业知识库（演示）',
    api_endpoint: 'http://demo.ragflow.local', api_key: 'demo-key-masked',
    is_active: true, ... },
];

// 关键词 → 回答的映射表，至少 10 条
export const MOCK_RAGFLOW_RESPONSES = {
  '年假': '根据《员工手册》第 5.2 条...',
  '报销': '差旅报销标准：交通、住宿、伙食补助分级别执行...',
  // ... 更多关键词
  '__default__': '（演示模式）当前未配置知识库对接。生产环境将返回基于 RAGFlow 检索的答案。',
};
```

### 4.2 拦截器匹配规则

| HTTP 方法 | URL 模式 | 返回 |
|---|---|---|
| GET | `/api/dify-apps/` | `{ results: MOCK_DIFY_APPS }` |
| GET | `/api/dify-apps/:id/` | `{ ...findById(MOCK_DIFY_APPS, id) }` |
| POST | `/api/dify-apps/` | `{ ...payload, id: nextId }`（创建演示） |
| PUT | `/api/dify-apps/:id/` | `{ ...findById, ...payload }`（更新演示） |
| DELETE | `/api/dify-apps/:id/` | `{}`（删除演示） |
| GET | `/api/ragflow-service/configs/` | `{ results: MOCK_RAGFLOW_CONFIGS }` |
| POST | `/api/ragflow-service/configs/:id/query/` | `{ answer: pickResponse(question), conversation_id: 'demo-conv-...' }` |

不匹配的 URL 透传，不影响其他功能。

## 5. 错误处理

- **mock 拦截器** — 始终返回 `status: 200`，让现有 UI 走正常路径
- **RagflowChatPage** — 现有 try/catch 在 demo 模式下不会触发错误 UI
- **DemoToggle 切换** — 弹出 Ant Design `message.info('已切换到演示模式 / 真实模式')`
- **DifyAppViewer iframe** — 若官方 demo URL 加载失败，沿用现有 `<div className="error-message">` 显示降级信息（不新增处理）

## 6. 测试策略

### 6.1 单元测试
- `demoInterceptor.test.js`：
  - 验证 7 类 URL 模式（GET 列表、GET 详情、POST 创建、PUT 更新、DELETE 删除、RAGFlow 列表、RAGFlow 查询）正确返回 mock
  - 验证 toggle 关闭时拦截器不生效
  - 验证不匹配的 URL 透传
- `AIShowcasePage.test.jsx`：
  - 渲染 1 个 Dify 卡片 + 1 个 RAGFlow 卡片
  - 点击 "立即体验" 跳转对应路由

### 6.2 E2E（可选）
- Playwright：进入 `/ai-showcase` → 开启 demo → 跳到 `/dify-apps` → 看到 3 个 mock 应用 → 点击进入 viewer

### 6.3 覆盖率目标
- 拦截器：100% 分支覆盖（纯函数逻辑）
- AIShowcasePage：≥80% 行覆盖

## 7. 可观测性

- 拦截器命中时 `logger.debug('[demo] intercepted', url)` — 不污染 console
- DemoToggle 状态写入 `localStorage['omnidesk:demo-mode']`
- 应用启动时读取 localStorage 还原偏好（避免刷新丢失）

## 8. 离线 / Windows 7 兼容性

- 纯前端 mock，不引入新 CDN 依赖
- Dify 官方 demo URL 通过 iframe 加载，不进 JS bundle
- Ant Design 5 + React 18 项目已有的浏览器适配，无需新增 polyfill

## 9. 实施步骤

1. 新建 `DemoContext` + `useDemoMode()` hook + localStorage 持久化
2. 新建 `demoMocks.js` + `demoInterceptor.js` + 单元测试
3. 在 `axiosConfig.js` 注册拦截器（追加在现有 refresh-token 拦截器之后）
4. 新建 `DemoToggle` 组件 + 嵌入 `Layout` 顶部右侧
5. 新建 `AIShowcasePage` + 路由 + 侧边栏菜单项
6. 运行 `npm test -- --coverage`，验证覆盖率
7. （可选）跑 Playwright E2E 验证完整流程

## 10. 风险与依赖

| 风险 | 缓解措施 |
|---|---|
| Dify 官方 demo URL 不稳定 | 用 2-3 个不同 demo URL 分散，失败时 iframe 显示降级文案 |
| 拦截器影响其他 axios 调用 | 严格 URL 模式匹配，未命中透传；单元测试覆盖 |
| localStorage 在隐私模式下不可用 | 捕获异常，回退到内存状态 |
| 与现有 refresh-token 拦截器冲突 | 注册顺序：先 mock 后 refresh-token，互不干扰 |

## 11. 边界（明确不做的事）

- 不部署真实 Dify / RAGFlow 服务
- 不修改后端任何代码
- 不引入 MSW 等重量级 mock 框架
- 不改写 `DifyAppManagementPage` / `DifyAppViewer` / `RagflowChatPage` 的业务逻辑
- 不提供"演示数据编辑器"（演示内容硬编码在 `demoMocks.js`）
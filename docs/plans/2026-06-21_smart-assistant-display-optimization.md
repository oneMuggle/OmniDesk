# 智能助手显示优化计划

## 背景与目标

当前智能助手在用户体验方面存在以下问题需要优化：

1. **流式输出体验**：虽然后端已实现 SSE 流式输出，但前端显示可能不够流畅，需要优化渲染体验
2. **think 内容显示**：当前 `<think>` 标签内容的显示方式需要改进，让用户更清晰地区分"思考过程"和"正式回答"
3. **取消功能缺失**：用户发送消息后无法取消 LLM 的回复，只能等待完成或关闭页面

## 涉及的文件与模块

### 前端
- `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx` — 主要聊天页面
- `omni_desk_frontend/src/shared/components/QuickAssistant.jsx` — 浮动助手组件
- `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js` — API 层
- `omni_desk_frontend/src/shared/components/ThinkContent.jsx` — think 内容组件
- `omni_desk_frontend/src/features/smart-assistant/components/MessageMarkdown.jsx` — Markdown 渲染

### 后端
- `omni_desk_backend/smart_assistant/views/chat.py` — 流式视图（可能需要添加客户端断开检测）
- `omni_desk_backend/smart_assistant/agent/orchestrator.py` — 编排器（检测客户端断开）

## 技术方案

### 1. 流式输出优化

**现状分析**：
- 后端已实现 SSE 流式输出 (`StreamingHttpResponse`)
- 前端使用 `fetch` + `ReadableStream` 接收
- 流式文本通过 `setStreamingAnswer(prev => prev + event.content)` 累加

**优化方案**：
- 确保流式接收逻辑稳定运行
- 优化 chunk 拼接，避免重复渲染
- 添加打字机效果（可选）

### 2. think 与正文分离显示

**现状分析**：
- 前端已有 `parseThinkContent()` 函数解析 `<think>` 标签
- `ThinkContent` 组件以可折叠方式显示思考过程
- 流式接收时实时解析

**优化方案**：
- 改进 `ThinkContent` 组件样式，使其更醒目
- 流式接收时，think 内容实时显示在单独的容器中
- 添加视觉区分（颜色、图标、动画）
- 支持默认折叠/展开配置

### 3. 取消功能

**前端实现**：
```javascript
// 使用 AbortController
const abortController = new AbortController();

fetch(url, {
  signal: abortController.signal,
  // ...其他配置
});

// 取消时
abortController.abort();
```

**UI 交互**：
- 发送消息后，发送按钮变为"停止"按钮
- 点击停止按钮取消请求
- 取消后显示"已取消"状态

**后端配合**：
- 检测客户端断开连接
- 优雅停止 LLM 流式生成
- 清理资源

## 实施步骤

### 阶段 1：取消功能（核心优先级）
- [x] 1.1 在 `smartAssistantApi.js` 中添加 AbortController 支持
- [x] 1.2 修改 `SmartChatPage.jsx` 流式接收逻辑，支持取消
- [x] 1.3 修改 `QuickAssistant.jsx` 同步支持取消
- [x] 1.4 添加"停止生成"按钮 UI
- [x] 1.5 处理取消后的状态清理

### 阶段 2：think 内容显示优化
- [x] 2.1 改进 `ThinkContent` 组件样式
- [x] 2.2 优化流式接收时 think 内容的实时解析和显示
- [x] 2.3 添加 think 区域的视觉区分效果

### 阶段 3：流式输出优化（验证和加固）
- [x] 3.1 验证当前流式输出是否正常工作
- [x] 3.2 修复可能存在的问题（如有）
- [x] 3.3 优化 chunk 渲染性能

### 阶段 4：后端优化（可选）
- [ ] 4.1 添加客户端断开检测
- [ ] 4.2 优化资源清理逻辑

## 风险评估与依赖

### 风险
1. **AbortController 兼容性**：现代浏览器都支持，Windows 7 Chrome 109 也支持
2. **流式稳定性**：需要确保网络中断等异常情况的处理
3. **后端改动**：客户端断开检测需要测试，确保不影响其他功能

### 依赖
- 无外部依赖
- 现有 SSE 协议无需修改

## 验收标准

1. 用户可以随时取消正在进行的 LLM 回复
2. think 内容与正文有明显的视觉区分
3. 流式输出流畅，无明显卡顿
4. 取消后界面状态正确，可以重新发送消息

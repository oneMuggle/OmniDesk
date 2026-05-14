# 清理冗余智能问答页 + 增强 Smart Assistant 思考过程展示

## 背景

前端 `/intelligent-chat` 页面是一个直接连接 Ollama/DeepSeek 的轻量级聊天，功能完全被 Smart Assistant (`/smart-assistant`) 覆盖。Smart Assistant 后端的 LLM（gemini-2.5-pro）原生支持 `<thinking>` 标签输出，流式接口已经正常工作，但前端尚未解析和展示思考过程。

## 目标

1. 删除冗余的 IntelligentChatPage 及其关联代码
2. 为 Smart Assistant 添加 `<thinking>` 标签解析和展示

## 修改文件清单

### 删除文件
- `omni_desk_frontend/src/shared/pages/IntelligentChatPage.jsx`
- `omni_desk_frontend/src/shared/pages/IntelligentChatPage.css`

### 修改文件
1. **`omni_desk_frontend/src/routes/index.js`** — 删除第13行 `IntelligentChatPage` import 和第315-317行路由
2. **`omni_desk_frontend/src/shared/config/menuConfig.js`** — 删除第45行 "智能问答" 菜单项
3. **`omni_desk_frontend/src/shared/context/ApiProvider.jsx`** — 简化：移除 ollama/deepseek/ragflow/dify 多提供商逻辑，移除 `getModels` 导入和导出，只保留 `conversationHistory` 状态
4. **`omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx`** — 添加 `<thinking>` 标签解析，复用 `ThinkContent` 组件展示思考过程

### 待确认的文件
- `src/shared/api/ollama.js` — 检查引用后决定删除
- `src/shared/api/deepseek.js` — 检查引用后决定删除
- `src/shared/components/SettingsPage.jsx` — 简化 API 配置部分
- `src/features/intelligent-chat/` — 整个目录可能可删除

## 实施步骤

- [x] 步骤 1：删除 IntelligentChatPage.jsx 和 .css
- [x] 步骤 2：清理路由和菜单（routes/index.js + menuConfig.js）
- [x] 步骤 3：简化 ApiProvider.jsx
- [x] 步骤 4：增强 SmartChatPage.jsx — 添加 parseThinkContent + ThinkContent 渲染
- [x] 步骤 5：清理孤立文件（SettingsPage.jsx, intelligent-chat/ 目录）
- [x] 步骤 6：前端构建验证 + 手动测试

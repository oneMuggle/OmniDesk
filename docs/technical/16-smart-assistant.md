# 智能助手系统

> 类似贾维斯的智能助手，通过聊天快速获取信息、知识库问答、文献搜索。

## 1. 架构概览

```
用户提问 → 意图分类(Ollama) → 工具路由 → 结果生成 → 返回答案
                                │
                    ┌───────────┼───────────────┐
                    ▼           ▼               ▼
               ScheduleTool  PersonnelTool    RAGTool
               (排班查询)     (人员查询)      (知识库/Ragflow)
```

### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| 意图分类器 | `smart_assistant/agent/intent_classifier.py` | Ollama 本地 LLM 识别用户意图 |
| 工具注册中心 | `smart_assistant/tools/registry.py` | 单例模式，动态注册工具 |
| 编排器 | `smart_assistant/agent/orchestrator.py` | 分类→路由→生成三段式流程 |
| Prompt 构建器 | `smart_assistant/agent/prompt_builder.py` | 根据意图构建 LLM prompt |
| Celery 任务 | `smart_assistant/tasks.py` | 文档向量化等异步任务 |

## 2. 后端实现

### 2.1 数据模型

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `AgentLog` | user, query, response, tool_used, tool_output, intent | 助手调用日志 |
| `SmartAssistantSession` | user, conversation_id, messages(JSON) | 对话会话 |
| `KnowledgeBaseDocument` | title, file, status, vectorized_at | 知识库文档 |

### 2.2 工具系统

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `ScheduleTool` | 排班/值班查询 | `events.Schedule` |
| `PersonnelTool` | 人员信息查询 | `personnel.Personnel` |
| `RAGTool` | 知识库问答 | Ragflow 向量数据库 |
| `DocumentTool` | 公文/文档搜索 | `documents` 模块 |
| `EventTool` | 事件/日程/节假日查询 | `events` 模块 |
| `MemoTool` | 备忘录查询 | `memos.Memo` |
| `ProjectTool` | 项目进度查询 | `projects.Project` |
| `NewsTool` | 新闻/通知搜索 | `news.NewsArticle` |

### 2.3 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/smart-assistant/chat/` | POST | 发送聊天消息 |
| `/api/smart-assistant/chat/` (SSE) | POST | 流式响应 |
| `/api/smart-assistant/sessions/` | GET/POST | 会话列表/创建 |
| `/api/smart-assistant/sessions/<id>/` | GET/DELETE | 会话详情/删除 |
| `/api/smart-assistant/knowledge-base/` | GET/POST | 知识库文档管理 |
| `/api/smart-assistant/logs/` | GET | 审计日志列表 |
| `/api/smart-assistant/logs/<id>/` | GET | 审计日志详情 |

## 3. 前端实现

| 组件 | 路径 | 说明 |
|------|------|------|
| `SmartChatPage` | `/smart-assistant` | 聊天主界面 |
| `QuickAssistant` | 全局浮动 | 快捷助手悬浮窗 |
| `ToolResult` | 共享组件 | 工具结果渲染（排班卡片/人员卡片等） |
| `KnowledgeBasePage` | `/knowledge-base` | 知识库管理 |
| `AgentLogPage` | 管理面板 | 审计日志面板 |

### 3.1 流式响应

- 后端：`StreamingHttpResponse` 按 chunk 推送
- 前端：`fetch` + `ReadableStream` 逐段渲染，打字效果

## 4. 配置

| 环境变量 | 说明 |
|----------|------|
| `SMART_ASSISTANT_DATASET_ID` | Ragflow 数据集 ID |
| `OLLAMA_ENDPOINT` | Ollama 本地服务地址 |
| `OLLAMA_MODEL` | Ollama 模型名称 |

## 5. 开发状态

| 阶段 | 状态 |
|------|------|
| Phase 1: 核心聊天 + 基础工具 | ✅ 已完成 |
| Phase 2: 知识库文档上传与向量化 | 🔄 部分完成（待配置 Dataset ID） |
| Phase 3: 流式响应 + 对话历史 | ✅ 已完成 |
| Phase 4: 审计面板 + 错误处理 | ✅ 已完成 |

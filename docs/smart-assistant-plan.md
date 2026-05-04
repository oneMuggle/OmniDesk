# 智能助手（Smart Assistant）实现方案

> 类似贾维斯的智能助手，通过聊天快速获取信息、知识库问答、文献搜索。

## 架构概览

```
用户提问 → 意图分类(Ollama) → 工具路由 → 结果生成 → 返回答案
                                │
                    ┌───────────┼───────────────┐
                    ▼           ▼               ▼
               ScheduleTool  PersonnelTool    RAGTool
               (排班查询)     (人员查询)      (知识库/Ragflow)
```

**核心组件：**
- **意图分类器** (`agent/intent_classifier.py`)：通过 Ollama 本地 LLM 识别用户意图（schedule_query / personnel_query / knowledge_qa / general_chat）
- **工具注册中心** (`tools/registry.py`)：单例模式，支持动态注册新工具
- **编排器** (`agent/orchestrator.py`)：分类 → 路由 → 生成的三段式流程
- **知识库** (`models.py` → KnowledgeBaseDocument)：文档上传 + Celery 异步向量化（Ragflow）

---

## Phase 1：核心聊天 + 基础工具 ✅ 已完成

### 后端 ✅
- [x] `smart_assistant` Django app 创建（models/serializers/views/urls/admin/apps/tasks）
- [x] 工具系统（base.py/registry.py/schedule_tool.py/personnel_tool.py/rag_tool.py）
- [x] 智能体（prompt_builder.py/intent_classifier.py/orchestrator.py）
- [x] `tasks.py` Celery 异步任务（文档向量化）
- [x] Django INSTALLED_APPS 注册 + URL include
- [x] 数据库迁移已生成（`migrations/0001_initial.py`）

### 前端 ✅
- [x] `SmartChatPage.jsx` + `.css`（聊天界面，含自动滚动）
- [x] `ToolResult.jsx` + `.css`（排班卡片/人员卡片/引用来源展示）
- [x] `smartAssistantApi.js`（API 调用层：聊天/上传/获取列表/删除文档）
- [x] 路由注册：`routes/index.js` 第 271-273 行 `/smart-assistant`
- [x] 侧边栏菜单入口：`Sidebar.jsx` 第 100 行 "AI 助手 → 智能助手"

---

## Phase 2：知识库文档上传与向量化集成 🔄 部分完成

### 后端 ✅ 已完成
- [x] `tasks.py` 完整实现：上传到 Ragflow → 获取文档 ID → 触发解析 → 状态流转
- [x] `views.py` KnowledgeBaseViewSet.perform_create 触发 Celery 任务
- [x] `settings/local.py` 添加 `SMART_ASSISTANT_DATASET_ID` 配置占位

### 前端 ✅ 已完成
- [x] `KnowledgeBasePage.jsx` 已创建（文档上传/列表/删除/状态轮询）
- [x] `KnowledgeBasePage.css` 样式文件
- [x] `routes/index.js` 注册 `/knowledge-base` 路由
- [x] `Sidebar.jsx` 侧边栏添加"知识库管理"菜单项

### 待配置 🔄 进行中
- [ ] `settings/local.py` 中填入真实的 `SMART_ASSISTANT_DATASET_ID`
- [ ] 确保 Celery worker 已启动

---

## Phase 3：流式响应 + 对话历史 ✅ 已完成

### SSE 流式响应 ✅
- [x] 后端：改用 `StreamingHttpResponse`，按 chunk 推送 LLM 输出
- [x] 前端：使用 `fetch` + `ReadableStream` 逐段渲染，加载状态改为流式打字效果

### 对话历史持久化 ✅
- [x] 后端：SmartAssistantSession 表增加 messages JSON 字段
- [x] 后端：每次交互追加到对话历史，支持按 conversation_id 恢复上下文
- [x] 前端：会话列表侧边栏 + 新建/切换会话

---

## Phase 4：审计面板 + 错误处理 ✅ 已完成

### AgentLog 审计面板 ✅
- [x] 后端：AgentLog 列表 API（支持按用户/时间/意图/关键词过滤）
- [x] 后端：AgentLog 详情 API（完整工具输入输出 + LLM 响应）
- [x] 前端：管理面板审计页面（表格 + 详情弹窗 + 过滤搜索）

### 错误处理与缓存 ✅
- [x] 工具调用失败时优雅降级（Ragflow 不可用时 fallback 到通用回答）
- [x] 用户友好的错误提示（区分网络错误/认证错误/服务不可用）
- [ ] 相同问题短时间内的缓存（暂不实现，优先级低）

---

## Phase 5：文献库搜索（仅设计，暂不开发）❌

### 设计概要
- `LiteratureSearchTool`：意图识别为 `literature_search` 时触发
- 支持数据源：CNKI、IEEE Xplore、PubMed、Google Scholar
- 适配器模式：`LiteratureSource` 抽象接口，各数据源实现 `search(query, filters)`
- `LiteratureSearchResult`：标题、作者、摘要、来源、URL、引用格式
- 前端：ToolResult 组件增加 literature 卡片展示

### 不开发原因
- CNKI/IEEE 等需要付费账号或 API 授权
- 需要处理反爬策略和请求频率限制
- 优先级低于内部知识库

---

## 文件清单

### 后端
```
omni_desk_backend/smart_assistant/
├── __init__.py
├── apps.py                    # SmartAssistantConfig + ready() 工具注册
├── models.py                  # KnowledgeBaseDocument, SmartAssistantSession, AgentLog
├── serializers.py             # 所有序列化器
├── views.py                   # SmartChatViewSet, KnowledgeBaseViewSet
├── urls.py                    # DefaultRouter 注册
├── admin.py                   # Django Admin 注册
├── tasks.py                   # Celery 异步任务（文档上传+解析）
├── migrations/
│   └── 0001_initial.py        # 数据库迁移
├── agent/
│   ├── prompt_builder.py      # 系统提示词 + 意图提示词
│   ├── intent_classifier.py   # Ollama 意图分类 + 答案生成
│   └── orchestrator.py        # 编排器（分类 → 路由 → 生成）
└── tools/
    ├── base.py                # BaseTool 抽象基类
    ├── registry.py            # ToolRegistry 单例
    ├── schedule_tool.py       # 排班查询（自然语言日期解析）
    ├── personnel_tool.py      # 人员查询（姓名搜索，脱敏）
    └── rag_tool.py            # Ragflow 知识库问答
```

### 前端
```
omni_desk_frontend/src/features/smart-assistant/
├── api/
│   └── smartAssistantApi.js   # API 调用层
├── pages/
│   ├── SmartChatPage.jsx      # ✅ 聊天页面
│   ├── SmartChatPage.css      # ✅ 聊天页面样式
│   ├── KnowledgeBasePage.jsx  # ✅ 知识库页面（待注册路由+样式）
│   └── KnowledgeBasePage.css  # ❌ 待创建
└── components/
    ├── ToolResult.jsx          # ✅ 工具结果展示
    └── ToolResult.css          # ✅ 工具结果样式
```

---

## 环境变量

```bash
# 后端
SMART_ASSISTANT_DATASET_ID=<ragflow-dataset-id>    # Ragflow 数据集 ID（需配置）

# 前端（已有）
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_OLLAMA_ENDPOINT=http://localhost:11434/api
REACT_APP_OLLAMA_MODEL=deepseek-r1:1.5b
```

---

## 统计

| 阶段 | 状态 | 进度 |
|------|------|------|
| Phase 1 核心聊天 + 基础工具 | ✅ 完成 | 100% |
| Phase 2 知识库集成 | ✅ 完成 | 100% |
| Phase 3 流式响应 + 对话历史 | ✅ 完成 | 100% |
| Phase 4 审计 + 错误处理 | ✅ 完成 | 95% |
| Phase 5 文献搜索 | 📝 仅设计 | 0% |

**整体进度：约 75%**

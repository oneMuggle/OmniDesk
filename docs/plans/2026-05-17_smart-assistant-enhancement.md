# 智能助手增强优化方案

> 日期：2026-05-17
> 状态：待评审

## 一、现状分析

### 当前架构

```
用户提问 → 意图分类(LLM) → 工具路由 → 执行工具 → LLM生成回答 → SSE流式返回
```

### 已有能力

| 模块 | 功能 | 状态 |
|------|------|------|
| smart_assistant | Agent编排 + 工具系统 | 已完成 |
| office_assistant | 文本校对/翻译/润色 | 已完成 |
| dify_apps | Dify应用iframe嵌入 | 已完成 |
| ragflow_service | Ragflow RAG配置+问答 | 已完成 |
| knowledge_base | 知识库文档管理+向量化 | 已完成 |

### 已有工具

| 工具 | 意图 | 功能 |
|------|------|------|
| schedule_tool | schedule_query | 查询排班/值班 |
| personnel_tool | personnel_query | 查询人员信息 |
| rag_tool | knowledge_qa | Ragflow知识库检索 |

### 存在的问题与不足

1. **工具数量少**：仅有3个工具，覆盖场景有限
2. **无多轮对话上下文**：每次对话独立，缺乏真正的多轮推理能力
3. **无函数调用(Function Calling)**：当前意图分类依赖prompt，不够精确
4. **前端交互单一**：主聊天页面缺乏消息操作（复制/重新生成/引用回复）
5. **无会话共享/协作**：会话仅限个人，无法分享给同事
6. **无快捷指令**：缺少预设的常用查询模板
7. **知识库体验弱**：文档上传后缺乏预览，向量化状态监控不够直观
8. **无对话统计**：缺少用量统计、热门问题、响应时间等运营数据
9. **Office助手依赖本地Ollama**：内网部署时若无Ollama则完全不可用

## 二、优化目标

1. 扩展工具生态，覆盖更多办公场景
2. 增强多轮对话体验
3. 改善前端交互细节
4. 增加运营统计能力
5. 提升系统可观测性和可靠性

## 三、优化方案

### Phase 1: 工具扩展（高优先级）

#### 1.1 新增业务工具

| 新工具 | 意图 | 描述 | 依赖 |
|--------|------|------|------|
| `document_tool` | document_search | 搜索公文/文档（标题/编号/类型/日期范围） | documents app |
| `event_tool` | event_query | 查询事件/日程（日期范围/类型/状态） | events app |
| `memo_tool` | memo_query | 查询备忘录/便签 | memos app |
| `project_tool` | project_status | 查询项目进度/状态/负责人 | projects app |
| `news_tool` | news_search | 搜索新闻/通知 | news app |

#### 1.2 工具改进

- **参数提取**：从用户query中自动提取结构化参数（使用LLM），而非简单关键词匹配
- **结果增强**：工具返回结果增加摘要字段，便于LLM更好地生成回答
- **错误处理**：工具执行失败时返回友好错误描述，而非直接抛出异常

#### 1.3 工具编排

- 支持**多工具组合调用**：一个用户问题可能涉及多个工具（如"查询张三的排班和项目"）
- 引入**并行工具调用**：多个无依赖的工具并行执行，减少响应时间

**涉及文件：**
- `omni_desk_backend/smart_assistant/tools/document_tool.py` [新建]
- `omni_desk_backend/smart_assistant/tools/event_tool.py` [新建]
- `omni_desk_backend/smart_assistant/tools/memo_tool.py` [新建]
- `omni_desk_backend/smart_assistant/tools/project_tool.py` [新建]
- `omni_desk_backend/smart_assistant/tools/news_tool.py` [新建]
- `omni_desk_backend/smart_assistant/agent/orchestrator.py` [修改]
- `omni_desk_backend/smart_assistant/agent/intent_classifier.py` [修改]
- `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` [修改]

**复杂度：中 | 预计工作量：2-3天**

---

### Phase 2: 多轮对话增强（高优先级）

#### 2.1 对话上下文管理

- `SmartAssistantSession.messages` 字段已存在(JSON格式)，但当前仅用于存储，未真正参与多轮推理
- **改进**：在 `orchestrator.process()` 中，将最近N条历史消息作为上下文传入LLM
- 支持**上下文窗口控制**：保留最近5轮或最近4000 tokens的消息历史

#### 2.2 对话能力增强

- **追问支持**：用户可以针对上一次回答继续提问（"这个人的电话是多少？"）
- **指代消解**：处理"他/她/这个/那个"等代词
- **话题切换检测**：识别用户是否开启了新话题，自动清空上下文

#### 2.3 前端会话体验

- **消息操作**：复制、重新生成、删除单条消息
- **引用回复**：针对某条消息进行回复
- **消息搜索**：在当前会话中搜索关键词
- **快捷指令**：预设常用问题模板（排班查询、人员查询等），一键发送

**涉及文件：**
- `omni_desk_backend/smart_assistant/agent/orchestrator.py` [修改]
- `omni_desk_backend/smart_assistant/agent/prompt_builder.py` [修改]
- `omni_desk_backend/smart_assistant/views/chat.py` [修改]
- `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx` [修改]
- `omni_desk_frontend/src/features/smart-assistant/components/MessageActions.jsx` [新建]
- `omni_desk_frontend/src/features/smart-assistant/components/QuickCommands.jsx` [新建]

**复杂度：高 | 预计工作量：3-4天**

---

### Phase 3: 运营统计（中优先级）

#### 3.1 用量统计

- 按日/周/月统计：
  - 对话次数
  - 活跃用户数
  - 平均响应时间
  - 各工具调用次数
  - Token消耗量（如API支持）

#### 3.2 热门问题排行

- 统计最高频的用户提问
- 统计最常触发的意图/工具
- 统计未匹配到意图的问题（"未识别问题"）

#### 3.3 统计API与前端

- 后端新增 `/api/smart-assistant/stats/` 端点
- 前端新增"智能助手统计"页面（管理员可见）
- 使用图表展示趋势（ECharts 或 Chart.js）

**涉及文件：**
- `omni_desk_backend/smart_assistant/views/stats.py` [新建]
- `omni_desk_backend/smart_assistant/urls.py` [修改]
- `omni_desk_frontend/src/features/smart-assistant/pages/StatsPage.jsx` [新建]
- `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js` [修改]

**复杂度：中 | 预计工作量：1-2天**

---

### Phase 4: 知识库体验优化（中优先级）

#### 4.1 文档预览

- 上传文档后支持在线预览（PDF/文本）
- 向量化状态实时更新（通过轮询或WebSocket）

#### 4.2 知识库增强

- 支持更多文档格式（.docx, .xlsx, .pptx）
- 文档分类/标签管理
- 检索结果高亮显示命中片段
- 支持知识库来源引用（LLM回答中标注引用了哪些文档）

**涉及文件：**
- `omni_desk_backend/smart_assistant/views/knowledge_base.py` [修改]
- `omni_desk_backend/smart_assistant/tasks.py` [修改]
- `omni_desk_frontend/src/features/smart-assistant/pages/KnowledgeBasePage.jsx` [修改]
- `omni_desk_frontend/src/features/smart-assistant/components/DocumentPreview.jsx` [新建]

**复杂度：中 | 预计工作量：2-3天**

---

### Phase 5: 系统可靠性（低优先级）

#### 5.1 LLM降级策略

- 主LLM端点不可用时，自动切换到备用端点
- 本地Ollama作为最后的fallback
- 前端显示当前使用的LLM端点信息

#### 5.2 速率限制

- 对聊天API添加速率限制（防止滥用）
- 可按用户/角色设置不同的请求频率限制

#### 5.3 缓存优化

- 常见问题答案缓存（Redis）
- 工具结果缓存（相同参数短时间内的重复调用）

**涉及文件：**
- `omni_desk_backend/smart_assistant/llm_service/router.py` [新建]
- `omni_desk_backend/smart_assistant/middleware/rate_limit.py` [新建]
- `omni_desk_backend/smart_assistant/views/chat.py` [修改]

**复杂度：中 | 预计工作量：1-2天**

---

## 四、实施优先级建议

| 优先级 | Phase | 原因 |
|--------|-------|------|
| P0 | Phase 1: 工具扩展 | 直接提升助手实用性，投入产出比最高 |
| P1 | Phase 2: 多轮对话 | 改善核心交互体验 |
| P2 | Phase 3: 运营统计 | 了解使用情况，为后续优化提供数据 |
| P3 | Phase 4: 知识库优化 | 提升RAG体验 |
| P4 | Phase 5: 可靠性 | 锦上添花，适合系统稳定后做 |

## 五、风险评估

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM API不稳定或费用高 | 核心功能不可用 | Phase 5降级策略，提前接入备用端点 |
| 多轮对话上下文过大 | 响应变慢、Token消耗增加 | 设置合理的上下文窗口大小（5轮或4000 tokens） |
| 工具扩展涉及多个Django app | 耦合度增加 | 工具仅读不写，通过Django ORM只读查询 |
| 内网无Ollama时办公助手不可用 | 功能降级 | 支持配置使用OpenAI-compatible端点替代 |

## 六、不涉及的范围

以下功能不在本次优化范围内（可作为未来方向）：

- 语音输入/输出（TTS/STT）
- 图片生成/理解
- 代码生成/执行
- 多模态对话
- 外部系统集成（邮件、钉钉、企微等）

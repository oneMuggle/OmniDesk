# 智能助手测试方案

> 生成日期：2026-05-07
> 目标：验证智能助手（Smart Assistant）各组件是否可用，并制定端到端测试计划
>
> ## 验证结果（2026-05-07 实测）
>
> | 测试项 | 状态 | 说明 |
> |--------|------|------|
> | OpenAI 客户端生成 | ✅ PASS | `OpenAIClient.generate()` 正确返回 Gemini 回答 |
> | OpenAI 客户端流式 | ✅ PASS | 正确解析 `delta.content`，自动过滤 `reasoning_content` |
> | 意图分类 - 排班 | ✅ PASS | "明天谁值班？" → `schedule_query` |
> | 意图分类 - 人员 | ✅ PASS | "张三在哪个部门？" → `personnel_query` |
> | 意图分类 - 通用 | ✅ PASS | "你好" → `general_chat` |
> | 意图标准化 | ✅ PASS | 自动转小写、空格→下划线 |
> | 编排器 - 通用对话 | ✅ PASS | `process()` 返回正确结构 |
> | 编排器 - 流式 SSE | ✅ PASS | `process_stream()` yield `meta → chunk → done` |
>
> **结论：核心链路（LLM → 意图分类 → 编排器 → SSE 流式）已验证可用。**

---

## 1. 可用性分析结论

### 1.1 整体结论：设计可用，但需适配 LLM 客户端

系统架构（意图分类 → 工具路由 → 答案生成）设计合理，各组件职责清晰，代码结构完整。但存在以下需要解决的问题：

### 1.2 核心问题清单

| # | 问题 | 严重性 | 涉及文件 | 说明 |
|---|------|--------|----------|------|
| 1 | LLM 客户端强绑定 Ollama | **CRITICAL** | `llm_service/ollama_client.py`, `agent/intent_classifier.py` | 当前使用 Ollama `/api/chat` 端点，需要适配为 OpenAI `/v1/chat/completions` 格式 |
| 2 | 意图分类返回值未做标准化 | **HIGH** | `agent/intent_classifier.py:19` | LLM 可能返回 `"Schedule Query"` 或带换行的字符串，直接用于工具匹配会失败 |
| 3 | 流式解析依赖 Ollama 响应格式 | **HIGH** | `ollama_client.py:32-37`, `agent/intent_classifier.py:55-56` | Ollama 流式返回 `chunk['message']['content']`，OpenAI 返回 `chunk['choices'][0]['delta']['content']` |
| 4 | SMART_ASSISTANT_DATASET_ID 为空 | **MEDIUM** | `settings/local.py:45` | Ragflow 数据集 ID 未配置，知识库上传功能不可用 |
| 5 | Celery worker 依赖 Redis | **MEDIUM** | `tasks.py` | 文档向量化需要 Celery + Redis |
| 6 | Ollama 环境变量仍存在 | **LOW** | `settings/base.py:292-293`, `.env` | 迁移后需清理或标注废弃 |

### 1.3 各组件可用性评估

| 组件 | 可用性 | 说明 |
|------|--------|------|
| 工具基类 `BaseTool` | ✅ 可直接使用 | 抽象设计合理 |
| 工具注册中心 `ToolRegistry` | ✅ 可直接使用 | 单例模式正确 |
| ScheduleTool | ✅ 可直接使用 | 依赖 `events.models.Schedule`，需确认数据库有数据 |
| PersonnelTool | ✅ 可直接使用 | 依赖 `personnel.models.Personnel`，需确认数据库有数据 |
| RAGTool | ⚠️ 需 Ragflow 配置 | 依赖 RagflowConfig 表和 SMART_ASSISTANT_DATASET_ID |
| 意图分类器 | ⚠️ 需适配 LLM 客户端 | 逻辑正确，但 LLM 调用方式需要改 |
| 编排器 `AgentOrchestrator` | ✅ 可直接使用 | 路由逻辑 + fallback 机制完整 |
| SSE 流式响应 | ⚠️ 需适配 LLM 客户端 | 框架正确，但流式解析依赖 Ollama 格式 |
| 会话管理 | ✅ 可直接使用 | 模型 + 视图完整 |
| AgentLog 审计 | ✅ 可直接使用 | 模型 + 视图 + 前端完整 |
| 前端 SmartChatPage | ✅ 可直接使用 | SSE 消费逻辑正确 |
| 前端 API 层 | ✅ 可直接使用 | axios + fetch 实现完整 |

---

## 2. 架构改造方案

### 2.1 LLM 客户端适配

当前 `OllamaClient` 需要替换或扩展为支持 OpenAI 兼容 API 的客户端。

**方案：创建新的 `OpenAIClient`，保留 `OllamaClient` 作为可选后端**

新增文件：`omni_desk_backend/llm_service/openai_client.py`

```python
# 关键差异对比
# Ollama: POST /api/chat → messages[{role, content}] → response['message']['content']
# OpenAI: POST /v1/chat/completions → messages[{role, content}] → choices[0]['message']['content']

# 流式差异：
# Ollama: chunk['message']['content']
# OpenAI: chunk['choices'][0]['delta']['content']
```

修改文件：`agent/intent_classifier.py`

- 将 `OllamaClient` 替换为 `OpenAIClient`
- 模型名称从环境变量读取（默认 `gemini-2.5-pro`）

### 2.2 意图分类返回值标准化

在 `classify_intent` 中增加标准化处理：

```python
return response.strip().lower().replace(' ', '_')
```

### 2.3 环境变量更新

在 `settings/local.py` 中添加：

```python
# 新的 LLM 配置
SMART_ASSISTANT_LLM_ENDPOINT = os.environ.get('SMART_ASSISTANT_LLM_ENDPOINT', 'https://gcli.ggchan.dev')
SMART_ASSISTANT_LLM_API_KEY = os.environ.get('SMART_ASSISTANT_LLM_API_KEY', '')
SMART_ASSISTANT_LLM_MODEL = os.environ.get('SMART_ASSISTANT_LLM_MODEL', 'gemini-2.5-pro')
```

---

## 3. 详细测试计划

### 3.1 测试环境准备

**前置条件：**
- [ ] Django 开发服务器运行（`python manage.py runserver`）
- [ ] 数据库已迁移（`python manage.py migrate`）
- [ ] 有测试用户账号 + JWT token
- [ ] 数据库中有排班数据（events.Schedule）
- [ ] 数据库中有人员数据（personnel.Personnel）
- [ ] .env 文件中配置 SMART_ASSISTANT_LLM_API_KEY

### 3.2 单元测试层（Python pytest）

#### T1：LLM 客户端测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_openai_client_generate` | 非流式调用 | 返回字符串回答 |
| `test_openai_client_generate_stream` | 流式调用 | 逐 chunk yield 内容 |
| `test_openai_client_timeout` | 超时处理 | 抛出异常，消息包含 "timeout" |
| `test_openai_client_auth_error` | 认证失败（无效 key） | 抛出异常，消息包含 "auth" 或 "401" |
| `test_openai_client_connection_error` | 连接失败（无效 URL） | 抛出 ConnectionError |

#### T2：意图分类器测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_classify_schedule` | "明天谁值班？" | 返回 `"schedule_query"` |
| `test_classify_personnel` | "张三是什么部门的？" | 返回 `"personnel_query"` |
| `test_classify_knowledge` | "公司的年假政策是什么？" | 返回 `"knowledge_qa"` |
| `test_classify_general` | "你好" | 返回 `"general_chat"` |
| `test_classify_fallback` | LLM 不可用时 | 返回 `"general_chat"`（异常安全） |

#### T3：工具测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_schedule_tool_today` | 查询今天排班 | 返回 found=True/False + 排班列表 |
| `test_schedule_tool_tomorrow` | 查询明天排班 | 正确解析"明天"关键词 |
| `test_schedule_tool_no_data` | 无排班日期的查询 | 返回 found=False |
| `test_personnel_tool_search` | 按姓名搜索 | 返回匹配的人员列表 |
| `test_personnel_tool_no_match` | 搜索不存在的人 | 返回 found=False |
| `test_tool_registry` | 注册和获取工具 | get_tool(intent) 返回正确实例 |

#### T4：编排器测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_orchestrator_schedule` | 排班问题端到端 | intent=schedule_query, tool_used=schedule_query |
| `test_orchestrator_personnel` | 人员问题端到端 | intent=personnel_query, tool_used=personnel_query |
| `test_orchestrator_general` | 通用问题 | intent=general_chat, tool_used=None |
| `test_orchestrator_stream` | 流式处理 | yield meta → chunks → done |
| `test_orchestrator_tool_fallback` | 工具失败（模拟 found=False） | 降级到通用回答，tool_fallback=True |

#### T5：视图层测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_chat_create` | POST /smart-assistant/chat/ | 200 + answer + intent |
| `test_chat_create_invalid` | 空 query | 400 错误 |
| `test_chat_stream` | POST /smart-assistant/chat/stream/ | 200 + text/event-stream |
| `test_session_crud` | 会话创建/列表/删除 | 正确 CRUD |
| `test_session_isolation` | 用户 A 看不到用户 B 的会话 | 数据隔离正确 |
| `test_agent_log_list` | AgentLog 列表 API | 返回列表 + 过滤生效 |

#### T6：模型测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_session_model` | 创建带 messages 的会话 | JSON 字段正确保存 |
| `test_agent_log_model` | 创建 AgentLog | 所有字段正确保存 |
| `test_knowledge_doc_model` | 创建文档记录 | 初始状态为 pending |

### 3.3 集成测试层

#### T7：端到端聊天流程

| 测试用例 | 步骤 | 预期结果 |
|----------|------|----------|
| `test_e2e_schedule_query` | 1. 登录获取 token → 2. POST 聊天请求 "明天谁值班？" → 3. 验证响应 | 返回排班信息，intent=schedule_query |
| `test_e2e_conversation` | 1. 发送第一轮问题 → 2. 使用返回的 conversation_id 发送第二轮 | 第二轮回答包含上下文 |
| `test_e2e_stream_response` | 1. POST 流式请求 → 2. 读取 SSE 事件流 | 依次收到 meta → chunk × N → session → done |

### 3.4 前端测试

#### T8：前端功能测试

| 测试用例 | 验证内容 | 预期结果 |
|----------|----------|----------|
| `test_chat_page_loads` | 页面渲染 | 显示"智能助手"标题和输入框 |
| `test_send_message` | 发送消息 | 用户消息上屏 + 收到回答 |
| `test_streaming_display` | 流式回答展示 | 打字效果 + 最终完整显示 |
| `test_session_list` | 打开会话面板 | 显示历史会话列表 |
| `test_tool_result_card` | 排班/人员结果展示 | ToolResult 组件正确渲染卡片 |

### 3.5 手动测试清单（浏览器 + Playwright）

| 测试场景 | 操作步骤 | 预期 |
|----------|----------|------|
| 排班查询 | 输入"明天谁值班？"，点击发送 | 显示排班卡片 + 自然语言回答 |
| 人员查询 | 输入"张三的信息"，点击发送 | 显示人员信息卡片 |
| 通用对话 | 输入"你好"，点击发送 | 显示通用回答 |
| 会话管理 | 新建会话 → 切换会话 → 删除会话 | 会话列表实时更新 |
| 错误处理 | 关闭 LLM 服务后发送请求 | 显示友好错误提示 |
| 流式响应 | 发送一个长问题 | 看到逐步打字效果 |

---

## 4. 实施优先级

### 阶段一：基础可用性（P0 - 必须先做）

1. 创建 OpenAI 客户端（`llm_service/openai_client.py`）
2. 修改 `intent_classifier.py` 使用新客户端
3. 增加意图返回值标准化
4. 配置环境变量（API key + 模型名）
5. 运行 T1-T6 单元测试验证基础功能

### 阶段二：端到端验证（P1）

6. 运行 T7 端到端集成测试
7. 运行 T8 前端功能测试
8. 手动测试清单验证

### 阶段三：可选增强（P2）

9. Ragflow 知识库集成测试（需要 Ragflow 环境）
10. Celery 异步任务测试
11. 性能测试（响应时间 < 5s）

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Gemini 模型响应延迟 | 用户体验差 | 设置合理超时，流式优先 |
| Gemini 的 reasoning_content 字段 | 流式解析可能混入思考过程 | 只提取 `delta.content`，忽略 `delta.reasoning_content` |
| 数据库缺少测试数据 | 工具返回空 | 准备 fixture 数据 |
| API key 额度限制 | 测试中断 | 使用 max_tokens 限制消耗 |

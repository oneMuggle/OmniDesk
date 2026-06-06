# 智能助手优化方案(2026-06-06)

## 背景与目标

`docs/smart-assistant-plan.md` 严重滞后于代码,实际 smart_assistant 模块已远超"75% 完成":

| 维度 | 计划文档描述 | 实际代码现状 |
|------|-------------|-------------|
| Agent 模块 | 3 个(prompt_builder/intent_classifier/orchestrator) | **7 个**,新增 conversation_context、rag_router、tool_chain_planner、tool_chain_executor |
| 工具 | 3 个(schedule/personnel/rag) | **12 个**,新增 document/event/meeting_room/memo/news/project/sensor |
| 视图 | 1 个 views.py | **6 个**,拆为 chat/knowledge_base/llm_config/logs/sessions/stats |
| 中间件 | 无 | **rate_limit**(30 req/min/user) |
| 缓存 | Phase 4 标为未实现 | **3 级缓存**(intent/tool/answer)已实装于 cache.py |
| 测试 | 5 个文件 975 行 | 5 个文件 975 行(无新增) |
| 覆盖率 | 计划文档未提 | **63.25%**(远低于项目基线 80.89%) |

**模块覆盖率断点**(`pytest --cov=omni_desk_backend.smart_assistant` 2026-06-06 实测,55 passed):

| 文件 | 覆盖率 | 缺行数 | 性质 |
|------|--------|--------|------|
| `views/llm_config.py` | 37% | 51/81 | LLM 多端点配置管理,核心 admin 功能 |
| `views/chat.py` | 48% | 50/97 | 核心对话入口,流式/非流式两路 |
| `views/stats.py` | 42% | 22/38 | 统计页 API |
| `tools/event_tool.py` | 32% | 19/28 | 事件/节假日工具 |
| `tools/sensor_tool.py` | 35% | 13/20 | 传感器工具 |
| `tools/document_tool.py` | 39% | 11/18 | 文档工具 |
| `tools/meeting_room_tool.py` | 33% | 18/27 | 会议室工具 |
| `tools/base.py` | 48% | 16/31 | 工具抽象基类 |
| `middleware/rate_limit.py` | 48% | 17/33 | 限流中间件 |
| `migrations/0004_llmendpoint_llmappconfig.py` | 52% | 11/23 | 数据迁移,业务关键 |

**本次优化目标:**

1. **质量与覆盖率补齐**:`smart_assistant` 模块总覆盖率从 63.25% 提升至 **≥85%**;通过专项测试守卫 CI
2. **功能扩展**:在不破坏现有架构前提下,新增 2-3 个高频业务工具(公告/合规/外部链接)
3. **性能与体验**:TTFT(首字延迟)降低 30%+;长会话管理;ToolResult 渲染性能优化
4. **架构升级**:从"单轮分类 + 链式工具"演进到"多轮规划 + 反思(Reflexion)",支持 LLM Tool Calling 标准协议
5. **文档同步**:废弃 `docs/smart-assistant-plan.md` 旧描述,产出新版"设计 + 现状"双视图

**不在本次范围:**

- 升级 LLM 底座(deepseek-r1:1.5b → 更大模型,单独立项)
- 引入 RAGFlow 之外的向量数据库(已有 ragflow_service)
- 升级 React 18 → 19、Django 4.2 → 5.x
- 引入微服务/前后端分离重构

---

## 涉及的文件与模块

### 后端(主要改动)

| 类别 | 路径 | 备注 |
|------|------|------|
| Agent | `omni_desk_backend/smart_assistant/agent/*.py` | 7 个模块,需补 orchestrator 边界 + tool_chain 解析失败路径测试 |
| Tools | `omni_desk_backend/smart_assistant/tools/*.py` | 12 个工具,7 个需补 test_tools 覆盖 |
| Views | `omni_desk_backend/smart_assistant/views/*.py` | 6 个视图,4 个覆盖率 < 65% |
| Middleware | `omni_desk_backend/smart_assistant/middleware/rate_limit.py` | 限流逻辑 + 429 响应测试 |
| Models | `omni_desk_backend/smart_assistant/models.py` | 仅 3% 缺口,补边界条件 |
| Cache | `omni_desk_backend/smart_assistant/cache.py` | 100% 覆盖,无需补 |
| 新工具(扩展) | `omni_desk_backend/smart_assistant/tools/{announcement,compliance,external_link}_tool.py` | 3 个新工具,新增 |
| Tool Calling 协议 | `omni_desk_backend/smart_assistant/agent/tool_calling.py`(新) | LLM 工具调用标准 |
| 反思模块 | `omni_desk_backend/smart_assistant/agent/reflexion.py`(新) | 自我评估与重试 |

### 前端

| 类别 | 路径 | 备注 |
|------|------|------|
| Pages | `omni_desk_frontend/src/features/smart-assistant/pages/*.jsx` | 4 个页面,首屏性能 + 长会话 |
| Components | `omni_desk_frontend/src/features/smart-assistant/components/*.jsx` | 5 个组件,ToolResult 渲染优化 |
| API | `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js` | 新增工具调用 API |
| Hooks | `omni_desk_frontend/src/features/smart-assistant/hooks/useChatStream.js`(新) | SSE + 重试/断线恢复 |

### 文档

| 路径 | 动作 |
|------|------|
| `docs/smart-assistant-plan.md` | 标为"已废弃",重定向到新文档 |
| `docs/technical/26-smart-assistant-architecture.md`(新) | 当前架构 + 设计决策 |
| `docs/technical/27-smart-assistant-tooling.md`(新) | 12+ 工具注册与扩展指南 |
| `docs/technical/28-smart-assistant-coverage-roadmap.md`(新) | 覆盖率补齐与守卫策略 |
| `docs/user-manual/04-smart-assistant-user-guide.md`(新) | 终端用户操作手册 |

---

## 技术方案

### 维度 1:质量与覆盖率补齐(P0,1 周)

**当前问题**:
- 模块覆盖率 63.25%,拖累项目基线(80.89%)+15 个百分点
- 现有 5 个测试文件覆盖了 happy path,但缺少以下场景:
  - LLM 客户端 mock 缺失,真实 LLM 调用可能造成测试慢/不可靠
  - 工具执行异常路径(`tool.execute` 抛异常时 fallback 行为)
  - 缓存命中/失效边界(空查询、超长查询)
  - 限流中间件 429 响应
  - 多工具链变量解析失败(`$tool_name.field` 不存在)
  - 流式响应断开/客户端中断

**方案**:

1. **抽取测试 fixture**(优先级最高)
   - `tests/conftest.py` 抽出 `mock_llm_router` fixture,所有 LLM 调用走 mock
   - `mock_tool_registry` fixture,允许测试时动态注册/替换工具
   - `mock_cache_backend` fixture,使用 Django locmem cache

2. **补充关键路径测试**(按文件分解):

   | 文件 | 缺什么 | 新增测试数估计 |
   |------|--------|--------------|
   | `views/chat.py` | 流式响应中断、conversation_id 不存在、消息超长截断、turn_count 累加 | +6 |
   | `views/llm_config.py` | 端点 CRUD、激活端点切换、健康检查 fallback、配置缓存失效 | +8 |
   | `views/stats.py` | 时间区间过滤、按用户聚合、零样本边界 | +5 |
   | `views/knowledge_base.py` | 上传失败重试、删除时 Celery 任务取消、空数据集 | +4 |
   | `tools/event_tool.py` | 日期范围解析、节假日边界、空查询 | +5 |
   | `tools/sensor_tool.py` | 设备 ID 不存在、离线设备、超时 | +4 |
   | `tools/document_tool.py` | 模板不存在、权限校验、关键词搜索 | +4 |
   | `tools/meeting_room_tool.py` | 时间冲突、空闲查询、容量过滤 | +5 |
   | `tools/base.py` | execute 异常处理、schema 生成 | +3 |
   | `middleware/rate_limit.py` | 30/min 上限、TTL 续期、未认证放行 | +4 |
   | `agent/orchestrator.py` | 工具链失败降级、缓存冲突、token 超限 | +6 |
   | `agent/tool_chain_planner.py` | JSON 解析失败、单工具降级为多工具 | +3 |
   | `agent/tool_chain_executor.py` | `$variable` 解析、依赖缺失、循环依赖检测 | +4 |
   | `migrations/0004` | 数据迁移幂等性、回滚路径 | +2 |
   | **合计** | | **+63** |

3. **覆盖率守卫**:
   - `pytest.ini` 添加 `--cov=omni_desk_backend.smart_assistant --cov-fail-under=85`
   - 在 `ci.yml` 的 coverage 步骤添加注释,标注"smart_assistant 模块门槛"
   - 渐进:本次先设 70%,下周推 80%,稳定后 85%

4. **失败重试与端到端**:
   - 添加 `test_e2e_smart_chat.py` 模拟"用户问排班 → 工具调用 → LLM 回答"全链路
   - 慢查询标记:任何 LLM mock 调用超过 100ms 触发警告(防止真实网络意外混入)

### 维度 2:功能扩展(P1,1.5 周)

**新工具(高频业务驱动)**:

1. **公告/通知工具** `announcement_tool.py`
   - 数据源:`communication` 应用的 Announcement 模型
   - 能力:查询最近 N 条公告、按标签过滤、统计已读率
   - 典型 query:"本周有什么公告?"、"安全相关的通知有哪些"
   - 权限:自动按 `request.user` 可见性过滤

2. **合规检查工具** `compliance_tool.py`
   - 数据源:`compliance` 应用(已有 InspectionRecord)
   - 能力:查询待整改项、检查某人合规分数、即将到期提醒
   - 典型 query:"张三还有几条待整改?"、"这周合规检查计划"
   - 集成度:中等,需验证 `compliance` 模型的 `select_related` 优化

3. **外部链接工具** `external_link_tool.py`
   - 数据源:`external-links` 应用的 Bookmark/LinkGroup
   - 能力:模糊匹配书签名、列出某分类链接、推荐相关链接
   - 典型 query:"公司 VPN 怎么登录?"、"研发部常用工具"

**工具注册协议增强**:
- 当前 `BaseTool` 缺少 `requires_auth` / `permission_check` 钩子
- 新增 `ToolContext` 抽象:`tool.execute(query, context={user, history, ...})`
- 默认拒绝跨用户数据泄露,工具内部显式使用 `context.user`

**新工具的单元 + 集成测试**(强制要求):
- 每个新工具必须有 ≥ 5 个测试用例(参数解析、权限、空结果、异常、并发)
- 接入 E2E:在 `test_e2e_smart_chat.py` 加 3 个场景

**多模态输入(可选,小步快跑)**:
- 聊天支持图片附件(先存 OSS 路径,LLM 调用时 inline)
- 需评估 Ollama 视觉模型支持情况(可能用 qwen-vl)

### 维度 3:性能与体验(P1,1 周)

**TTFT 优化**:

| 手段 | 预期收益 | 实施 |
|------|----------|------|
| Prompt prefix caching(Ollama) | -30% TTFT | 启用 `OLLAMA_KEEP_ALIVE=24h`,固定 system prompt |
| 工具结果预序列化 | -50ms/请求 | `cache.py` 中预热 5 分钟内热点 |
| 同步首字 token 协议 | -100ms | SSE 第一帧先发 `meta`,客户端立即渲染骨架 |
| 并发预取(意图 + 工具 schema) | -80ms | `process()` 内并行化分类 + schema 拉取 |

**长会话管理**:
- 当前 `SmartAssistantSession.messages` 直接 JSONField 全量存,无压缩
- 引入"消息窗口":保留最近 10 轮,超出后总结为 system message
- 实现 `compress_history(messages, max_tokens=2000)` 工具函数
- 配置项 `SMART_ASSISTANT_MAX_HISTORY_TOKENS=2000`

**前端体验**:
- ToolResult 渲染性能:`React.memo` + 卡片数据 hash 比对,避免父组件更新触发重渲染
- 长消息虚拟滚动:`react-window` 集成,超过 200 条消息启用
- 流式中断恢复:`fetch` 失败后 3 次重试,带指数退避
- 加载骨架:首字到达前显示工具意图 + schema 预览

**性能验证**:
- 接入 `django-silk`(路线图阶段 2 已选,本次复用)
- 关键指标:`/api/smart-assistant/chat/stream/` P50/P95、首字节时间
- 跑 benchmark 脚本 `scripts/bench_smart_assistant.py`,记录到 `docs/technical/29-bench-results.md`

### 维度 4:架构升级(Agent 框架)(P2,2 周)

**当前架构**:
- 单轮意图分类 + 工具链(plan → execute → synthesize)
- 错误处理:工具失败 → 通用回答
- 反思:无

**目标架构(渐进)**:

```
User Query
   │
   ▼
┌──────────────────┐
│  Intent Classify │  ← 已有,加强多意图识别
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Plan Generator  │  ← 已有 tool_chain_planner,扩展为支持 ReAct
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Step Executor   │  ← LLM Tool Calling 标准协议
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Reflexion       │  ← 新增:结果质量评估,失败自动重规划
└────────┬─────────┘
         │
         ▼
   Final Answer
```

**P2.1 LLM Tool Calling 标准协议**:
- 当前 `tool_chain_planner` 用 prompt 让 LLM 输出 JSON
- 升级:如果 LLM 端点支持原生 function calling(Ollama 0.4+),用结构化工具描述
- 兼容层:fallback 到 JSON 解析,保证现有 LLM 可用
- 新增 `agent/tool_calling.py` 抽象接口

**P2.2 Reflexion 反思**:
- 工具结果不满足时,LLM 自评"这个结果是否回答了用户问题"
- 不满意:重规划(最多 2 次),最终降级到通用回答
- 自我评估结果写入 `AgentLog.tool_reflexion` 字段(JSONField,记录每轮评估)

**P2.3 工具执行超时与并发**:
- 当前 `tool.execute` 串行,长工具(文档生成)阻塞
- 引入 `asyncio` + `ThreadPoolExecutor`,独立工具并行
- 单工具超时 10s,超时即视为"未找到"触发降级

**P2.4 可观测性**:
- 整合结构化日志(路线图阶段 4 已选 `python-json-logger`)
- 关键事件:tool 调度耗时、LLM token 消耗、缓存命中率、reflexion 触发率
- 暴露 `/api/smart-assistant/metrics/` Prometheus 端点(可选)

**架构升级的兼容性保障**:
- 新增开关:`SMART_ASSISTANT_AGENT_VERSION=v1|v2`
- v1 = 当前实现(默认),v2 = 新 ReAct+Reflexion
- 通过 feature flag 灰度,生产先跑 10% 流量

---

## 实施步骤(分阶段)

### 阶段 1:文档同步(0.5 天)— P0

- [ ] 在 `docs/smart-assistant-plan.md` 顶部加废弃声明:"本文件已过期,最新版见 docs/technical/26-smart-assistant-architecture.md"
- [ ] 创建 `docs/technical/26-smart-assistant-architecture.md` — 当前真实架构与设计决策
- [ ] 创建 `docs/technical/27-smart-assistant-tooling.md` — 12 工具清单 + 扩展指南
- [ ] 创建 `docs/user-manual/04-smart-assistant-user-guide.md` — 用户视角的操作手册
- [ ] 在 `docs/technical/README.md` 章节表添加上述文档链接

### 阶段 2:覆盖率补齐(1 周)— P0

- [ ] 抽取 fixtures:`tests/conftest.py` 中 `mock_llm_router` / `mock_tool_registry` / `mock_cache_backend`
- [ ] 补充 `views/chat.py` 测试(+6)
- [ ] 补充 `views/llm_config.py` 测试(+8)
- [ ] 补充 `views/stats.py` 测试(+5)
- [ ] 补充 `views/knowledge_base.py` 测试(+4)
- [ ] 补充 7 个工具的测试(+30)
- [ ] 补充 `tools/base.py` 测试(+3)
- [ ] 补充 `middleware/rate_limit.py` 测试(+4)
- [ ] 补充 `agent/orchestrator.py` 边界测试(+6)
- [ ] 补充 `agent/tool_chain_*.py` 测试(+7)
- [ ] 补充 `migrations/0004` 幂等性测试(+2)
- [ ] 新增 `tests/test_e2e_smart_chat.py` — 全链路 E2E(+3)
- [ ] 在 `pytest.ini` 加 `--cov-fail-under=70`(临时门槛)
- [ ] 跑测试:`pytest --cov` 应显示 smart_assistant ≥ 85%
- [ ] 提门槛到 80% → 85%
- [ ] 总测试数 55 → 130+(无回归)

### 阶段 3:新工具(1.5 周)— P1

- [ ] 设计新工具 schema:`announcement_tool.py` / `compliance_tool.py` / `external_link_tool.py`
- [ ] 评估数据源(对应 app 的可见性规则、权限要求)
- [ ] 实现 `announcement_tool.py` + 注册 + 8 个测试
- [ ] 实现 `compliance_tool.py` + 注册 + 8 个测试
- [ ] 实现 `external_link_tool.py` + 注册 + 8 个测试
- [ ] 在 `tools/registry.py` 注册新工具(已用 ready 钩子)
- [ ] 在 `agent/prompt_builder.py` 的工具描述列表追加
- [ ] E2E 测试覆盖 3 个新工具(+3)
- [ ] 前端 `ToolResult.jsx` 增加新卡片类型(`AnnouncementCard` / `ComplianceCard` / `LinkCard`)

### 阶段 4:性能优化(1 周)— P1

- [ ] 启用 Ollama prompt caching:`OLLAMA_KEEP_ALIVE=24h` + 固定 system prompt
- [ ] `cache.py` 预热:在 `apps.py` ready 时加载 5 分钟内热点 query
- [ ] `process()` 并发化:`concurrent.futures.ThreadPoolExecutor` 并行意图分类 + schema
- [ ] SSE 首字加速:第一帧先发 `meta` 含工具意图,客户端立即渲染骨架
- [ ] 长会话压缩:`compress_history()` 工具 + `SMART_ASSISTANT_MAX_HISTORY_TOKENS` 配置
- [ ] 前端 ToolResult `React.memo` 优化
- [ ] 长消息虚拟滚动:`react-window` 集成
- [ ] 流式中断恢复:fetch + 指数退避重试
- [ ] 性能 benchmark 脚本:`scripts/bench_smart_assistant.py`
- [ ] 跑前后对比,记录到 `docs/technical/29-bench-results.md`

### 阶段 5:架构升级(2 周)— P2

- [ ] 设计 `agent/tool_calling.py` 抽象接口(协议 + JSON 兼容层)
- [ ] 实现 Tool Calling 协议:检测 LLM 端点能力,优先用原生 function calling
- [ ] 实现 `agent/reflexion.py`:LLM 自评 + 重规划
- [ ] 工具并发执行:`asyncio` + `ThreadPoolExecutor`
- [ ] 工具超时:10s/工具,超时降级
- [ ] AgentLog 增加 `tool_reflexion` 字段(迁移)
- [ ] 特征开关:`SMART_ASSISTANT_AGENT_VERSION=v1|v2`
- [ ] 灰度方案:10% → 50% → 100% 流量
- [ ] 可观测性:`/api/smart-assistant/metrics/` Prometheus(可选)
- [ ] 兼容性测试:v1 vs v2 行为对照(同 query,同 answer 或在 80% 相似度内)

### 阶段 6:CI 守卫与回归(0.5 天)— P0

- [ ] `ci.yml` 在 coverage 步骤加注释指向 `pytest.ini` 的 smart_assistant 门槛
- [ ] 添加专门的 GitHub Action:`smart-assistant-coverage.yml`,每周一生成覆盖率报告
- [ ] 跑完整测试套:确认无回归(总测试数 ≥ 130,覆盖率 ≥ 80%)
- [ ] 安全扫描:`pip-audit` + `bandit -r omni_desk_backend/smart_assistant/`

---

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| 覆盖率门槛 85% 提升后存量 PR 失败 | MEDIUM | 渐进 70→80→85,提前 1 周通知 |
| 新工具数据源权限/可见性错误导致越权 | **HIGH** | 严格走 `ToolContext.user`;新增工具前 24 小时 code review;E2E 用例必须包含"非授权用户被拒" |
| Tool Calling 协议升级破坏现有 LLM 客户端 | MEDIUM | 兼容层 + 特征开关,灰度发布 |
| Reflexion 重规划导致响应时间翻倍 | MEDIUM | 限重试次数(≤2),超时降级;前端显示"思考中"状态 |
| Prompt caching 命中率低,TTFT 未改善 | LOW | 监控命中率 < 30% 时回滚 |
| 长会话压缩损失上下文 | LOW | 仅压缩超 10 轮的历史,关键事实保留 |
| 多模态输入引入新依赖 | LOW | 暂不在 v1 范围,放 P3 阶段 |
| 新工具数据量大导致 N+1 | MEDIUM | 严格 `select_related` / `prefetch_related`,在 PR review 检查 |

---

## 依赖

### 后端
- 已有:`django`、`djangorestframework`、`requests`、`langchain`(可能)
- 新增:
  - `asyncio-throttle`(限流并发,可选)
  - `prometheus-client`(可选,生产可观测)
  - `pytest-asyncio`(测试异步路径)

### 前端
- 已有:React 18、Ant Design 5、React Query v5
- 新增:
  - `react-window`(长消息虚拟滚动)
  - (可选)`react-virtuoso` 备选

### 文档
- 无新依赖

### 工具
- Ollama 本地 LLM(已是项目标配)
- 可选:qwen-vl(多模态,P3 阶段评估)

---

## 验收标准

### 阶段 1-2 完成时(P0)

- [ ] `docs/technical/26-smart-assistant-architecture.md` 等 3 份文档已创建
- [ ] `docs/smart-assistant-plan.md` 顶部有废弃声明
- [ ] `pytest --cov=omni_desk_backend.smart_assistant --cov-fail-under=85` 通过
- [ ] 总测试数 55 → 130+,无回归
- [ ] 项目整体覆盖率 ≥ 80.89%(保持基线)
- [ ] CI 在 smart_assistant 模块的覆盖率门槛通过

### 阶段 3 完成时(P1)

- [ ] 3 个新工具(announcement/compliance/external_link)已实现并注册
- [ ] 每个新工具 ≥ 5 个单元测试 + ≥ 1 个 E2E
- [ ] 前端 ToolResult 支持 3 种新卡片
- [ ] 用户可以问"这周有什么公告"获得正确答案

### 阶段 4 完成时(P1)

- [ ] TTFT P50 降低 ≥ 30%(对比基线)
- [ ] 工具结果缓存命中率 ≥ 40%
- [ ] 100 轮长对话不卡顿(`compress_history` 工作正常)
- [ ] 前端 ToolResult 重渲染次数 < 5/分钟
- [ ] 流式响应中断后 3 次内恢复

### 阶段 5 完成时(P2)

- [ ] Tool Calling 协议在支持的 LLM 上启用,fallback 兼容
- [ ] Reflexion 触发后能在 2 次重试内给出答案或优雅降级
- [ ] 工具并发执行,平均工具调用时间降低 ≥ 25%
- [ ] v1/v2 灰度对比测试通过(80% 相似度)
- [ ] `/api/smart-assistant/metrics/` 暴露关键指标(可选)

### 阶段 6 完成时(P0)

- [ ] CI 工作流通过,无回归
- [ ] `bandit -r omni_desk_backend/smart_assistant/` 0 高危问题
- [ ] `pip-audit` 无新增高危依赖
- [ ] GitHub Action 周报自动生成

---

## 时间估算

| 阶段 | 范围 | 工作量 | 累计 |
|------|------|--------|------|
| 阶段 1 文档同步 | 0.5 天 | 0.5 | 0.5 天 |
| 阶段 2 覆盖率补齐 | 1 周 | 5.0 | 5.5 天 |
| 阶段 3 新工具 | 1.5 周 | 7.5 | 13.0 天 |
| 阶段 4 性能优化 | 1 周 | 5.0 | 18.0 天 |
| 阶段 5 架构升级 | 2 周 | 10.0 | 28.0 天 |
| 阶段 6 CI 与回归 | 0.5 天 | 0.5 | 28.5 天 |
| **总计** | **约 6 周** | | |

## 优先级矩阵

| 阶段 | 业务价值 | 实施成本 | 风险 | 建议顺序 |
|------|----------|----------|------|----------|
| 1 文档同步 | 中 | 极低 | 极低 | 第 1 |
| 2 覆盖率补齐 | 高(回归守卫) | 中 | 低 | 第 2 |
| 6 CI 守卫 | 中 | 低 | 极低 | 穿插于 2 |
| 3 新工具 | 高(直接业务) | 中 | 中 | 第 3 |
| 4 性能优化 | 中(体验提升) | 中 | 低 | 第 4 |
| 5 架构升级 | 中(长期能力) | 高 | 中 | 第 5 |

---

## 与现有计划的关系

- **独立于** `docs/plans/2026-06-05_project-optimization-roadmap.md`
  - 路线图阶段 1 提到"补 smart_assistant/agent/*.py(10-49% → 50%+,高复杂)"
  - 本计划作为该高复杂项的**细化子方案**,但独立执行,有自己的优先级
- **覆盖** `docs/smart-assistant-plan.md`
  - 旧文件标为废弃,所有内容迁移到 `docs/technical/26-*`
- **复用** 路线图已选依赖
  - `pytest-cov`(覆盖率,本次强化阈值)
  - `django-silk`(性能,阶段 4 接入)
  - `python-json-logger`(日志,阶段 5 整合)

---

## 不在本计划内

- LLM 底座升级(deepseek-r1:1.5b → 更大模型)— 单独立项,需先评估 token 成本
- 多模态(图像/语音输入)— 评估 Ollama qwen-vl 支持,放 P3
- Agent 自主学习/微调— 涉及训练数据收集,架构级变更
- 智能助手移动端适配— 项目无 mobile-first 需求
- 跨用户/跨部门对话共享— 安全合规评估,需合规部门参与
- 商业 LLM 接入(GPT-4、Claude)— 项目硬约束:内网离线,排除

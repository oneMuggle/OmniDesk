# L1 原生 Function Calling / Tool Use 协议 — 设计文档

> 📅 **日期**:2026-08-06
> **作者**:AI 中台规划(基于 2026-08-06 差距分析报告)
> **状态**:✅ 已批准,待编写实施计划
> **优先级**:P0(12 项 P0 缺口之一)
> **预计工时**:1.5-2 周(2 个 sprint)

## 1. 目标与背景

### 1.1 现状

`llm_service/router.py` 仅支持纯 chat completions,从未向 `tools=[...]` / `tool_choice` 传参;工具调用完全靠应用层"自实现"——LLM 输出 JSON,后端解析,无原生 function calling 协议。

**关键文件**:`omni_desk_backend/llm_service/router.py`、`smart_assistant/agent/orchestrator.py`

### 1.2 问题

1. 现有 18 个 BaseTool 必须人工构造 prompt 内嵌的工具调用指令,LLM 容易"想当然"产生伪 JSON
2. 结构化工具描述、参数校验、断路器由 OmniDesk 自维护,**未享受 OpenAI / Anthropic / Gemini 各家模型的标准能力**
3. 无法做模型 A/B 评估(协议层不同模型自带格式不同)
4. 与 Dify / Coze / n8n 等业界"AI 中台"差距显著(Dify 2024 起原生支持)

### 1.3 目标

为 LLM router 添加 OpenAI 兼容协议的 `tools=[...]` / `tool_choice` 原生调用支持,**复用现有 18 个 BaseTool 与 ToolRegistry**,**保留 JSON fallback 路径作 A/B**,**支持完整 E2E 打通**。

### 1.4 范围

**包含 ✅**

- OpenAI 协议层原生 tool_calls 支持
- BaseTool 增加 `get_openai_tool_schema()` 静态方法(18 个工具)
- ToolRegistry 自动拼装 `tools=[]` 参数
- LLM router 在 tool_calls=true 时返回结构化结果
- 后端二次 tool_calls 循环(最多 3 轮)
- 工具选择决策日志(新增 `AgentLog.tool_calls_meta`)
- JSON 路径作为 fallback + settings 开关 + doctor 汇报
- Mock LLM server 扩展模拟 tool_calls 响应
- E2E 测试覆盖 4 个完工标准

**不包含 ❌(留待后续子项目)**

- Anthropic tool_use / Gemini function_calling 的差异化适配(留 L1.1)
- MCP 客户端(留 L3)
- 工具/插件市场 UI(留 L4)
- 长上下文工具调用压缩策略(留 L2 联动)
- 数字员工 Persona 接入工具调用(留 L5)

### 1.5 约束

- Python 3.10 / Django 4.2 / PostgreSQL(`CLAUDE.md`)
- requirements.in 由 pip-compile 管理(NEVER 编辑 .txt)
- mock_llm_server 已在 `smart_assistant/tests/mock_llm_server.py` 实现,需扩展不重写
- 内网离线部署,无外网依赖(新增 SDK 必须本地 pip 安装)
- Win7 兼容(本节不涉及前端)
- 中文为主

## 2. 整体架构

```
┌─ 智能助手 chat 请求 ──────────────────────────────────┐
│ POST /api/smart-assistant/chat/                       │
│ POST /api/smart-assistant/chat/stream/                │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌─ AgentOrchestrator.process() / process_stream() ──────┐
│  ├─ 1. 路由决策:TOOL_CALLS_PATH or JSON_PATH           │
│  │     (settings.USE_NATIVE_TOOL_CALLS + endpoint 能力)│
│  ├─ 2a. [NEW] tool_calls 路径                          │
│  │     ├─ ToolRegistry.get_openai_tools() → tools=[..] │
│  │     ├─ LLMRouter.generate(tools=..., tool_choice=..)│
│  │     ├─ 收到 finish_reason=tool_calls / tool 消息    │
│  │     ├─ 解析 tool_call_id + name + arguments(JSON)  │
│  │     ├─ ToolRegistry.get_tool_for_user(name, user)  │
│  │     ├─ tool.execute(arguments, context)            │
│  │     ├─ tool 消息 append 到 messages[]               │
│  │     ├─ 进入下一轮(MAX_TOOL_CALLS_ROUNDS=3)         │
│  │     └─ 最终 LLM 生成自然语言回答                    │
│  ├─ 2b. [OLD] JSON 路径(fallback,A/B 评估期保留)      │
│  └─ 3. 写 AgentLog(含 tool_calls_meta) + 返回         │
└────────────────────────────────────────────────────────┘

       ┌────────────────────┐         ┌─────────────────────┐
       │ llm_service/router │ ←────── │ Mock LLM Server     │
       │ generate(tools=..) │         │ tests/mock_llm_     │
       │                    │         │ server.py [扩展]    │
       └────────────────────┘         └─────────────────────┘
                │
                ▼
       ┌────────────────────┐
       │ BaseTool           │ ←── get_openai_tool_schema()
       │ .get_openai_tool_  │     (新增,静态方法,返回
       │  schema()          │      {"type":"function",
       │                    │       "function":{"name":..,
       │                    │       "description":..,
       │                    │       "parameters":JSONSchema}})
       └────────────────────┘
```

### 关键设计点

1. **路由开关**:`settings.USE_NATIVE_TOOL_CALLS=True` 时走新路径,`False` 时保留 JSON 路径;A/B 评估期两个并存
2. **端点能力检测**:`LlmEndpoint.model_capabilities` 新增 `native_tool_calls: bool`,老端点(false)强制走 JSON 路径
3. **最大轮次**:`MAX_TOOL_CALLS_ROUNDS=3` 防止死循环,3 轮后 LLM 必须给最终回答
4. **降级策略**:第一轮 tool_calls 失败 → 自动切到 JSON 路径(per-request,不污染下次)

## 3. 详细组件设计

### 3.1 `BaseTool.get_openai_tool_schema()` —— 18 个工具的协议化出口

```python
# smart_assistant/tools/base.py(新增,BaseTool 上)

class BaseTool(ABC):
    # ... 现有字段:name / description / intent_type / risk_level ...

    @classmethod
    @abstractmethod
    def get_openai_tool_schema(cls) -> dict:
        """返回 OpenAI 兼容的 tool 描述。

        返回结构:
        {
            "type": "function",
            "function": {
                "name": cls.intent_type,          # 与 intent_type 对齐
                "description": "调度查询...",
                "parameters": {                    # JSON Schema (Draft 7)
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "..."},
                        "date_from": {"type": "string", "format": "date"},
                        ...
                    },
                    "required": ["query"],
                },
                "strict": True,                    # OpenAI structured outputs
            },
        }
        """
```

**关键决策**

| 决策 | 选择 | 理由 |
|---|---|---|
| schema 字段名 | `name = intent_type`(如 `schedule_query`) | 与现有 intent 路由键对齐,**避免维护两套命名空间** |
| 参数描述来源 | 子类 `_describe_parameters()` 静态方法返回 | 比 introspect inspect.signature 更可控,**避免误把 context/历史参数暴露给 LLM** |
| JSON Schema 严格模式 | `strict: True` | OpenAI 2024-08+ 支持,**降低幻觉**,Anthropic/Gemini 自动忽略(降级) |
| 嵌套参数 | `additionalProperties: false`(每层都加) | strict 必需,否则 OpenAI 报错 |
| 鉴权/上下文参数 | **不暴露**给 LLM(user/scope/history 在 system prompt 或 tool_context 注入) | LLM 看到的"参数"只有它真正能控制的 query/date_from 等 |
| `validate_arguments(args)` 归属 | `BaseTool` 上,默认实现基于 `get_openai_tool_schema()` 的 `parameters` 字段自动生成 JSON Schema 校验器 | 单一来源 schema,无需每个工具重写校验;子类可覆盖以加入业务校验(如 PersonnelTool 检查人员存在) |

**18 个工具改造工作量(粗估)**

- 7 个工具参数简单(`ScheduleTool/EventTool/MemoTool/NewsTool/MeetingRoomTool/AnnouncementTool/ExternalLinkTool`)—— 每个 ~10 行 `_describe_parameters()`
- 6 个中等(`PersonnelTool/ProjectTool/ComplianceTool/SensorTool/RAGTool/DocumentTool`)—— 每个 ~20 行
- 3 个 office 工具(`OfficeReadTool/OfficeGenerateTool/SpreadsheetTool`)—— 已有 schema,但要适配 strict 模式,~15 行/个
- 2 个非典型(`RAGTool` 多数据集选择 / `OfficeGenerateTool` 写文件)—— 需要在 schema 中显式声明"禁止 destruct 字段"

**总计**:~250 行新代码,18 个工具各加 1 个静态方法。

### 3.2 `ToolRegistry.get_openai_tools(user)` —— 自动拼装 + 用户级过滤

```python
# smart_assistant/tools/registry.py(扩展)

class ToolRegistry:
    def get_openai_tools(self, user) -> list[dict]:
        """返回当前用户可用的 OpenAI 协议 tools 列表。

        流程:
        1. 遍历 self._tools(全局 18 个)
        2. 跳过 BaseTool.required_auth 且未登录用户
        3. 跳过 user.has_perm 校验未通过的(若工具定义了 perm 字段)
        4. 调 cls.get_openai_tool_schema() 收集
        5. 按 risk_level 排序(read-only 在前,write/destructive 在后)

        返回:List[{"type":"function", "function": {...}}]
        """
```

**与现有 `get_tool_for_user(intent_type, user)` 互补**:后者按意图找单个工具(用于 JSON 路径);前者按用户拉全集(用于 LLM 决策)。

**角色级白名单**:角色 (`RoleProfile.allowed_tools`) 决定 LLM 看到的工具集。多 Agent 场景中,Supervisor 用全集,Worker 用子集。

### 3.3 `LLMRouter.generate()` —— 新增 `tools` 与 `tool_choice` 参数

```python
# llm_service/router.py(扩展签名)

def generate(
    self,
    messages: list[dict],
    *,
    app_name: str = "smart_assistant",
    tools: list[dict] | None = None,        # NEW
    tool_choice: str | dict | None = None,  # NEW: "auto" | "none" | {"type":"function","function":{"name":..}}
    stream: bool = False,
    **kwargs,
) -> tuple[str, dict, list[dict]]:
    """现在如果 tools 非空,会透传到 OpenAI 兼容 endpoint。

    返回值扩展(原 (content, usage)):
    (content, usage, tool_calls)
    其中 tool_calls=[{"id":.., "type":"function","function":{"name":..,"arguments":..}}]
    """
```

**Ollama 兜底的处理**:Ollama 0.5+ 已支持 OpenAI 兼容 `/v1/chat/completions` 的 tools 参数,直接透传;Ollama 不支持的旧版本自动降级到 JSON 路径。

### 3.4 `AgentOrchestrator` —— 新增 `tool_calls` 主循环

```python
# smart_assistant/agent/orchestrator.py(新增方法)

class AgentOrchestrator:
    MAX_TOOL_CALLS_ROUNDS = 3  # 防死循环

    def _process_tool_calls_path(
        self, *, query, context, tools_schema, llm_messages
    ) -> tuple[str, dict]:
        """tool_calls 主循环。

        伪代码:
        for round_idx in range(MAX_TOOL_CALLS_ROUNDS):
            content, usage, tool_calls = router.generate(
                messages=llm_messages, tools=tools_schema, tool_choice="auto"
            )

            if not tool_calls:
                # LLM 主动选择不调用工具,直接返回 content
                return content, usage

            # 记录决策日志
            self._log_tool_call_decision(round_idx, tool_calls)

            # 第二轮及之后仍传 tools,LLM 可能继续调其他工具;但若发现 LLM
            # 重复调同一工具,doctor 自检会报告"工具循环嫌疑"。
            next_messages = llm_messages + [{
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            }] + tool_results

            # 继续下一轮(MAX_TOOL_CALLS_ROUNDS=3 硬上限,见 §9 风险)

            # 执行每个 tool_call
            tool_results = []
            for tc in tool_calls:
                tool = registry.get_tool_for_user(tc.function.name, context.user)
                if tool is None:
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": "tool_unavailable_for_user"}),
                    })
                    continue

                # 参数校验(基于 schema,严格模式)
                try:
                    args = json.loads(tc.function.arguments)
                    validated = tool.validate_arguments(args)  # NEW
                except (json.JSONDecodeError, ValidationError) as e:
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": "invalid_arguments", "detail": str(e)}),
                    })
                    continue

                # 执行(走现有 execute_with_guard + Hook 系统)
                result = tool.execute_with_guard(validated, context)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # 把 assistant(tool_calls) + tool 结果 append 到 messages
            llm_messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })
            llm_messages.extend(tool_results)

        # 3 轮后 LLM 仍调工具 → 兜底:让 LLM 强制自然语言回答
        content, usage, _ = router.generate(
            messages=llm_messages, tool_choice="none"  # 强制
        )
        return content, usage
```

**JSON 路径保留为 `_process_json_path()`**,两者互斥,settings 切换。

### 3.5 数据模型扩展

```python
# smart_assistant/models.py:AgentLog(扩展)

class AgentLog(models.Model):
    # ... 现有字段 ...

    # NEW: 工具调用路径与决策日志
    tool_call_path = models.CharField(
        max_length=16, choices=[("native","native"),("json","json"),("none","none")],
        default="none", blank=True,
    )
    tool_calls_meta = models.JSONField(
        default=list, blank=True,
        help_text="[{"round":0,"tool":"schedule_query","arguments":{...},"duration_ms":123}]"
    )
    tool_calls_rounds = models.IntegerField(default=0)
```

**迁移**:`smart_assistant/migrations/00XX_native_function_calling.py`,**仅新增字段 + index,不破坏旧数据**。

### 3.6 settings 扩展

```python
# omni_desk_backend/settings/base.py(新增)

USE_NATIVE_TOOL_CALLS = True  # 默认开,旧端点自动降级
MAX_TOOL_CALLS_ROUNDS = 3     # 全局上限
TOOL_CALLS_TIMEOUT_SECONDS = 30  # 单次工具调用 + LLM 轮次的总预算
```

**端点能力检测**:`doctor.py` 启动时调 `POST /v1/chat/completions` 带一个最小 tool,验证是否返回 `tool_calls`。结果缓存到 `LlmEndpoint.model_capabilities.native_tool_calls`(新增字段,迁移)。

## 4. 数据流(端到端)

**典型场景:用户问"明天的排班"**

```
1. POST /api/smart-assistant/chat/  {message: "明天的排班"}
   ↓
2. AgentOrchestrator.process()
   ├─ 检查 USE_NATIVE_TOOL_CALLS=True
   ├─ context = ToolContext(user, scope=resolve_scope(user))
   ├─ tools_schema = ToolRegistry.get_openai_tools(user)  # 18 个 schema
   └─ llm_messages = [
        {"role":"system", "content":"你是 OmniDesk 助手..."},
        {"role":"user", "content":"明天的排班"},
      ]
   ↓
3. LLMRouter.generate(messages, tools=tools_schema, tool_choice="auto")
   → 响应:
     {
       "choices": [{
         "finish_reason": "tool_calls",
         "message": {
           "role": "assistant",
           "content": null,
           "tool_calls": [{
             "id": "call_abc",
             "type": "function",
             "function": {"name":"schedule_query","arguments":"{\"date\":\"2026-08-07\"}"}
           }]
         }
       }],
       "usage": {"prompt_tokens":180,"completion_tokens":25,"total_tokens":205}
     }
   ↓
4. _process_tool_calls_path() 解析 → ScheduleTool.execute({"date":"2026-08-07"}, context)
   ├─ Hook PRE_EXECUTE → AuditLogHook 记录
   ├─ tool.execute_with_guard(...) → 查 DB 返回 [{"shift":"早班", "user":"张三"}]
   └─ Hook POST_EXECUTE → PiiMaskingHook 脱敏
   ↓
5. tool 消息追加:
   llm_messages.append({"role":"assistant", "content":null, "tool_calls":[...]})
   llm_messages.append({"role":"tool", "tool_call_id":"call_abc", "content":"[{...}]"})
   ↓
6. 第二轮 LLMRouter.generate(messages, tool_choice="auto")  # 自然语言总结
   → 响应: content="明天是张三早班", usage={...}
   ↓
7. 写 AgentLog(tool_call_path="native", tool_calls_meta=[{round:0, tool:"schedule_query"...}], estimated_cost=...)
   ↓
8. 响应 {"answer":"明天是张三早班","tool_used":"schedule_query","tool_calls_meta":[...]}
```

**轮次限制触发的兜底**

```
若 3 轮后 LLM 仍想调工具:
  → 第四轮 router.generate(messages, tool_choice="none")  # 强制自然语言
  → tool_calls_rounds=3 标记到 AgentLog
  → 若仍失败 → 走现有 _resolve_error() 错误分类
```

## 5. 错误处理

| 失败场景 | 行为 | 用户感知 |
|---|---|---|
| 端点不支持 tool_calls | router 自动降级到 JSON 路径 | 无感知,AgentLog.tool_call_path="json" |
| LLM 返回的 arguments 非合法 JSON | 该 tool_call 标记 invalid_arguments,继续下一轮 | LLM 重试或切换工具 |
| 工具名 LLM 编造(typo) | `registry.get_tool_for_user()` 返回 None → 注入 tool_unavailable_for_user 错误消息 | LLM 通常自动重选 |
| 用户无权限调该工具 | 同上,工具名合法但权限不够 | 同上,日志 audit |
| 单轮工具执行超时 | 现有 `TimeoutGuardHook` 兜底,返回 `{"error":"tool_timeout"}` | LLM 通常会换工具或告知用户 |
| 3 轮后 LLM 仍调工具 | 第 4 轮强制 tool_choice="none" | LLM 给出基于已有 tool 结果的回答 |
| LLM 调用本身 5xx | 现有端点降级链路(Ollama 兜底) | 现有 fail-closed 行为 |
| 流式路径(SSE)中途 tool_calls | SSE done 帧带 `finish_reason=tool_calls` + 内部继续 2 轮后最终回答 | 用户看到"打字中"短暂停顿后出最终答案 |

**所有错误均带 `kind`/`hint` 字段**(沿用现有契约),前端 `resolveErrorHint` 复用。

## 6. 测试策略

### 6.1 单元测试(18 个工具 × 1 schema 测试 = 18 个)

```python
# smart_assistant/tests/test_openai_tool_schemas.py

@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_schema_is_valid_openai_function(tool_cls):
    schema = tool_cls.get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == tool_cls.intent_type
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]
    assert schema["function"]["parameters"]["type"] == "object"
    assert "required" in schema["function"]["parameters"]
    assert schema["function"].get("strict") is True

    # JSON Schema 严格模式必备:每层 additionalProperties=false
    _assert_strict(schema["function"]["parameters"])

def _assert_strict(node):
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False
        for prop in node.get("properties", {}).values():
            _assert_strict(prop)
    elif node.get("type") == "array":
        _assert_strict(node["items"])
```

### 6.2 Mock LLM 扩展(模拟 tool_calls 响应)

```python
# smart_assistant/tests/mock_llm_server.py(扩展)

# 现有 keyword→固定回答,扩展为 keyword→tool_calls 序列:
TOOL_CALL_SCENARIOS = {
    "明天排班": [{
        "finish_reason": "tool_calls",
        "message": {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "call_test_001",
                "type": "function",
                "function": {
                    "name": "schedule_query",
                    "arguments": json.dumps({"date": "2026-08-07"})
                }
            }]
        }
    }, {  # 第二轮返回自然语言
        "finish_reason": "stop",
        "message": {"role": "assistant", "content": "明天是张三早班"}
    }],
    # ... 覆盖 schedule/personnel/rag/memo 等典型意图
}
```

### 6.3 E2E 测试(`test_native_function_calling_e2e.py`,8 个用例)

| 用例 | 验证 |
|---|---|
| `test_happy_path_single_tool` | LLM 调 1 个工具 → 后端执行 → 第二轮自然语言回答 |
| `test_two_tools_parallel` | LLM 1 轮调 2 个工具(并行)→ 2 个 tool 消息 → 总结 |
| `test_invalid_arguments_lmm_recovers` | arguments JSON 不合法 → tool 注入 invalid_arguments → LLM 自动重试 |
| `test_unauthorized_tool_blocked` | LLM 调到用户无权工具 → 注入 tool_unavailable → LLM 换工具 |
| `test_max_rounds_fallback` | Mock LLM 永远返回 tool_calls → 3 轮后强制 tool_choice=none → 兜底回答 |
| `test_json_path_fallback` | 旧端点(无 tool_calls 能力)→ 自动降级到 JSON 路径 → AgentLog.tool_call_path="json" |
| `test_streaming_with_tool_calls` | SSE 路径中途 tool_calls → done 帧带 finish_reason → 第二轮在 chat 层完成 |
| `test_decision_log_persisted` | AgentLog.tool_calls_meta 含每轮的 round/tool/arguments/duration_ms |

### 6.4 A/B 评估钩子(留接口,不强制启用)

```python
# smart_assistant/agent/orchestrator.py

def process(self, ...):
    if settings.USE_NATIVE_TOOL_CALLS and endpoint_has_tool_calls:
        return self._process_tool_calls_path(...)
    return self._process_json_path(...)  # fallback
```

通过 env var 切换,无需代码改动即可对比两条路径的回答质量。

## 7. 迁移计划

**新增迁移**(`smart_assistant/migrations/00XX_native_function_calling.py`):

```python
operations = [
    migrations.AddField(
        model_name="agentlog",
        name="tool_call_path",
        field=models.CharField(max_length=16, default="none", blank=True),
    ),
    migrations.AddField(
        model_name="agentlog",
        name="tool_calls_meta",
        field=models.JSONField(default=list, blank=True),
    ),
    migrations.AddField(
        model_name="agentlog",
        name="tool_calls_rounds",
        field=models.IntegerField(default=0),
    ),
    migrations.AddField(
        model_name="llmendpoint",
        name="model_capabilities",
        field=models.JSONField(default=dict, blank=True, help_text='{"native_tool_calls": true/false}'),
    ),
]
```

**无破坏性**:全部 nullable / default,旧数据兼容;旧端点 `model_capabilities={}` → 自动判 false → 走 JSON 路径。

## 8. 影响面与依赖

| 模块 | 改动 |
|---|---|
| `smart_assistant/tools/*.py` | 18 个文件加 1 个静态方法,共 ~250 行 |
| `smart_assistant/tools/registry.py` | 加 `get_openai_tools()` |
| `smart_assistant/tools/base.py` | 加 `get_openai_tool_schema()`(默认 raise `NotImplementedError`,**非** `@abstractmethod`)与 `validate_arguments()`(默认按 `parameters` 做 jsonschema 校验,**非** abstract) |
| `smart_assistant/agent/orchestrator.py` | 加 `_process_tool_calls_path()` + `_process_json_path()` 重构 |
| `llm_service/router.py` | `generate()` 签名扩展 + OpenAI tools 透传 |
| `smart_assistant/models.py` | AgentLog 3 字段 + LlmEndpoint 1 字段 |
| `smart_assistant/views/doctor.py` | 新增 `native_tool_calls` 检查项 |
| `smart_assistant/views/chat.py` | 无变化(走 orchestrator) |
| `smart_assistant/views/tasks.py` | 多 Agent 路径同样改造 |
| `smart_assistant/cache.py` | cache_key 加 `tool_call_path` 维度 |
| `smart_assistant/tests/mock_llm_server.py` | 加 TOOL_CALL_SCENARIOS |
| `smart_assistant/tests/test_openai_tool_schemas.py` | 新文件 |
| `smart_assistant/tests/test_native_function_calling_e2e.py` | 新文件 |
| `omni_desk_backend/settings/base.py` | 3 个新 settings |
| `docs/technical/16-smart-assistant.md` | 加 §13 章节 |
| `docs/user-manual/08-smart-assistant-usage.md` | 用户视角:工具调用响应可能更长(1-2 轮) |

**依赖项**:零新依赖(OpenAI 协议是 HTTP JSON,无需 SDK)

## 9. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| LLM 在新协议下产生幻觉工具名 | `registry.get_tool_for_user()` 不存在时返回 None → 注入 tool_unavailable → LLM 重选 | settings `USE_NATIVE_TOOL_CALLS=False` 立即回 JSON 路径 |
| 严格 JSON Schema 触发 OpenAI 端 400 | schema 生成器有单元测试覆盖;首轮上线时灰度(仅 staff 用户) | 同上 |
| 工具调用增加 1-2 轮 LLM 调用,延迟变高 | `MAX_TOOL_CALLS_ROUNDS=3` 硬上限;首轮只对 `is_staff=True` 启用收集数据 | settings 关掉 |
| 18 个工具 schema 描述质量低 → LLM 选错工具 | 编写 prompt:每个工具 description 至少 1-2 句中文说明 + 示例 query;单元测试覆盖 schema 字段 | 灰度发布,doctor 自检 |
| 多 Agent 路径工具选择不一致 | `agents/roles.py` `RoleProfile.allowed_tools` 作为白名单,`ToolRegistry.get_openai_tools()` 自动按角色过滤 | 暂时禁用多 Agent 路径,仅单 Agent |

**回滚演练**:settings 切换 1 行即可,doctor 自检 `native_tool_calls` 状态实时刷新。

## 10. 验收清单(对应 4 个完工定义)

- [ ] **LLM 原生 tool_calls + 后端路由 + E2E 打通** —— `test_happy_path_single_tool` + `test_two_tools_parallel` 通过
- [ ] **BaseTool 适配 OpenAI 协议 schema 输出** —— `test_openai_tool_schemas.py` 18 个工具全部 pass
- [ ] **ToolChain 适配 + 工具选择决策日志** —— `tool_calls_meta` 字段写入,`test_decision_log_persisted` 通过
- [ ] **保留 JSON 路径作 fallback + 可 A/B** —— `test_json_path_fallback` 通过,settings 切换无需重启

## 附录 A:18 个工具 schema 设计样例(ScheduleTool 完整示意)

```python
class ScheduleTool(BaseTool):
    intent_type = "schedule_query"
    risk_level = RISK_LEVEL_READ

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询排班/值班信息。支持日期范围、人员姓名、班次类型过滤。"
                    "示例 query: '明天的排班'、'本周张三的值班'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询,可含日期/人员/班次关键词",
                        },
                        "date_from": {
                            "type": "string",
                            "format": "date",
                            "description": "起始日期(ISO 8601),可选",
                        },
                        "date_to": {
                            "type": "string",
                            "format": "date",
                            "description": "结束日期(ISO 8601),可选",
                        },
                        "personnel_name": {
                            "type": "string",
                            "description": "人员姓名,精确匹配",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    @classmethod
    def _describe_parameters(cls) -> dict:
        # ... 同上,用于 base.py 注册 ...
```

> 其余 17 个工具按此模板,按工作量分级实施。

## 附录 B:与现有架构的兼容矩阵

| 现有机制 | tool_calls 路径下的行为 | JSON 路径下的行为 |
|---|---|---|
| Hook 系统(pre/post/on_failure) | ✅ 完整保留 | ✅ 不变 |
| `risk_level` + `require_confirmation` | ✅ `require_confirmation=True` 的工具在 tool_calls 路径走 confirm-replay(复用现有 `_process_json_path` 兜底逻辑) | ✅ 不变 |
| scope 三级隔离 | ✅ `ToolRegistry.get_openai_tools()` 自动按 user 过滤 | ✅ 不变 |
| 缓存(`cache.py`) | ⚠️ cache_key 加 `tool_call_path` 维度,避免 A/B 切换污染 | ✅ 不变 |
| Mock LLM e2e 测试 | ✅ 扩展 TOOL_CALL_SCENARIOS | ✅ 已有测试保留 |
| Doctor 自检 | ✅ 新增 `native_tool_calls` 检查项 | ✅ 不变 |
| 多 Agent(`MultiAgentExecutor`) | ⚠️ 阶段 1 同步改造,阶段 2 增加 RoleProfile 角色级白名单 | ✅ 不变 |

---

> **下一步**:本文档经用户复核后,调用 superpowers:writing-plans 技能产出 `docs/superpowers/plans/2026-08-06-native-function-calling.md` 实施计划(含按 sprint 拆分的可独立验证任务)。
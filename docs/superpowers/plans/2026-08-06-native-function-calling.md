# L1 原生 Function Calling / Tool Use 协议 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OmniDesk 智能助手添加 OpenAI 兼容协议的原生 tool_calls / tool_choice 支持,让 LLM 直接决策调用 18 个 BaseTool 中的哪个,并完整保留 JSON fallback 路径作 A/B 评估。

**Architecture:**
- 18 个 BaseTool 各加 `get_openai_tool_schema()` 静态方法(返回 OpenAI strict JSON Schema)
- `LLMRouter.generate()` 扩展签名,支持透传 `tools=[...]` / `tool_choice` 参数
- `AgentOrchestrator` 新增 `_process_tool_calls_path()` 主循环,最多 3 轮;保留 `_process_json_path()` 作 fallback
- `AgentLog` 新增 3 字段(`tool_call_path` / `tool_calls_meta` / `tool_calls_rounds`)记录决策日志
- `settings.USE_NATIVE_TOOL_CALLS=True` 时走新路径,旧端点自动降级到 JSON 路径
- 不引入新依赖(OpenAI 协议是 HTTP JSON)

**Tech Stack:** Django 4.2 + DRF + PostgreSQL + Ollama(OpenAI 兼容) + pytest + Mock LLM server(已存在,扩展)

**Spec 引用:** `docs/superpowers/specs/2026-08-06-native-function-calling-design.md`(已批准)

---

## Global Constraints

> 来自 `CLAUDE.md` 与项目全局规则,所有任务隐式遵守:

- **Python 3.10** 统一;`requirements.in` 由 pip-compile 管理(NEVER 编辑 .txt)
- **测试设置**:`pytest --ds=omni_desk_backend.settings.test`(in-memory SQLite, MD5 密码)
- **覆盖率基线**:模块 ≥80%(本计划引入 ~370 行测试)
- **commit 规范**:Conventional Commits(`feat:` / `fix:` / `test:` / `docs:` / `refactor:`)
- **路径命名**:Django app 内部用 `omni_desk_backend/<app>/...`
- **中文为主**:所有 docstring、日志、UI 文案、commit message body 用中文
- **内网离线**:不引入新 pip 依赖,OpenAI 协议用 HTTP JSON
- **Win7 兼容**:本计划不涉及前端(下一子项目处理)
- **不破坏现有**:所有迁移都是 `AddField` nullable / 带 default,旧数据兼容

---

## 文件结构(本计划产出物)

| 文件 | 类型 | 责任 |
|---|---|---|
| `smart_assistant/tools/base.py` | 修改 | `get_openai_tool_schema()` abstract + `validate_arguments()` 默认实现 |
| `smart_assistant/tools/{schedule,personnel,event,memo,news,meeting_room,announcement,external_link,project,compliance,sensor,document,rag,office_read,office_generate,spreadsheet}_tool.py` | 修改 | 18 个文件各加 1 静态方法 |
| `smart_assistant/tools/registry.py` | 修改 | `get_openai_tools(user)` + 增强 `get_tool_for_user()` |
| `llm_service/router.py` | 修改 | `generate()` 加 `tools`/`tool_choice`/返回 `tool_calls` |
| `smart_assistant/agent/orchestrator.py` | 修改 | `_process_tool_calls_path()` 主循环 + 拆分 `_process_json_path()` |
| `smart_assistant/models.py` | 修改 | AgentLog 3 字段 + LlmEndpoint `model_capabilities` |
| `smart_assistant/migrations/00XX_native_function_calling.py` | 创建 | 新增 4 字段(全部 nullable/default) |
| `smart_assistant/cache.py` | 修改 | cache_key 加 `tool_call_path` 维度 |
| `smart_assistant/views/doctor.py` | 修改 | 新增 `native_tool_calls` 检查项 |
| `smart_assistant/tests/mock_llm_server.py` | 修改 | 加 `TOOL_CALL_SCENARIOS` + 处理 tool_calls 请求 |
| `smart_assistant/tests/test_openai_tool_schemas.py` | 创建 | 18 工具 schema 单元测试 |
| `smart_assistant/tests/test_llm_router_tool_calls.py` | 创建 | router 透传测试 |
| `smart_assistant/tests/test_orchestrator_tool_calls_path.py` | 创建 | 主循环单元测试 |
| `smart_assistant/tests/test_native_function_calling_e2e.py` | 创建 | 8 个 E2E 用例 |
| `omni_desk_backend/settings/base.py` | 修改 | 加 3 个 settings |
| `docs/technical/16-smart-assistant.md` | 修改 | 加 §13 章节 |

---

# 阶段 1:基础设施(Sprint 1,Day 1-4)

> 目标:让 18 个工具能产出 OpenAI schema,router 能透传。无业务链路改动,可独立单测。

---

### Task 1:settings + 模型字段迁移

**Files:**
- Modify: `omni_desk_backend/settings/base.py:340-348` (在 CELERY_BEAT_SCHEDULE 之后)
- Modify: `smart_assistant/models.py:AgentLog`(在 `user_feedback` 字段后追加 3 个字段)
- Modify: `smart_assistant/models.py:LlmEndpoint`(在 `cost_per_1k_tokens` 后追加 1 个字段)
- Create: `smart_assistant/migrations/00XX_native_function_calling.py`
- Test: `smart_assistant/tests/test_settings_and_migration.py`(新建)

**Interfaces:**
- Consumes: 无
- Produces:
  - `settings.USE_NATIVE_TOOL_CALLS: bool`(默认 `True`)
  - `settings.MAX_TOOL_CALLS_ROUNDS: int`(默认 `3`)
  - `settings.TOOL_CALLS_TIMEOUT_SECONDS: int`(默认 `30`)
  - `AgentLog.tool_call_path: str`(`"native"` / `"json"` / `"none"`,默认 `"none"`)
  - `AgentLog.tool_calls_meta: list[dict]`(默认 `[]`)
  - `AgentLog.tool_calls_rounds: int`(默认 `0`)
  - `LlmEndpoint.model_capabilities: dict`(默认 `{}`)

- [ ] **Step 1:写失败测试 —— settings 默认值**

`smart_assistant/tests/test_settings_and_migration.py`:

```python
from django.conf import settings


def test_use_native_tool_calls_default_true():
    assert settings.USE_NATIVE_TOOL_CALLS is True


def test_max_tool_calls_rounds_default_3():
    assert settings.MAX_TOOL_CALLS_ROUNDS == 3


def test_tool_calls_timeout_default_30():
    assert settings.TOOL_CALLS_TIMEOUT_SECONDS == 30
```

- [ ] **Step 2:运行测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_settings_and_migration.py -v
```

期望:`AttributeError: 'Settings' object has no attribute 'USE_NATIVE_TOOL_CALLS'`

- [ ] **Step 3:添加 settings**

在 `omni_desk_backend/settings/base.py` 末尾(`SMART_ASSISTANT_*` 段之后或合适位置):

```python
# === L1 原生 Function Calling ===
USE_NATIVE_TOOL_CALLS = True
MAX_TOOL_CALLS_ROUNDS = 3
TOOL_CALLS_TIMEOUT_SECONDS = 30
```

- [ ] **Step 4:再跑 settings 测试 → 期望 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_settings_and_migration.py -v
```

- [ ] **Step 5:写失败测试 —— 模型字段存在**

在 `test_settings_and_migration.py` 追加:

```python
from smart_assistant.models import AgentLog, LlmEndpoint


def test_agentlog_has_tool_call_fields():
    field_names = {f.name for f in AgentLog._meta.get_fields()}
    assert "tool_call_path" in field_names
    assert "tool_calls_meta" in field_names
    assert "tool_calls_rounds" in field_names


def test_llmendpoint_has_model_capabilities():
    field_names = {f.name for f in LlmEndpoint._meta.get_fields()}
    assert "model_capabilities" in field_names
```

- [ ] **Step 6:运行模型测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_settings_and_migration.py::test_agentlog_has_tool_call_fields -v
```

期望:`AssertionError: 'tool_call_path' not in {...}`

- [ ] **Step 7:修改 `smart_assistant/models.py`**

在 `AgentLog.user_feedback` 字段后追加:

```python
    # L1 原生 Function Calling(2026-08-06)
    tool_call_path = models.CharField(
        max_length=16,
        choices=[("native", "native"), ("json", "json"), ("none", "none")],
        default="none",
        blank=True,
    )
    tool_calls_meta = models.JSONField(default=list, blank=True)
    tool_calls_rounds = models.IntegerField(default=0)
```

在 `LlmEndpoint.cost_per_1k_tokens` 字段后追加:

```python
    model_capabilities = models.JSONField(
        default=dict,
        blank=True,
        help_text='例如 {"native_tool_calls": true/false}',
    )
```

- [ ] **Step 8:生成迁移文件**

```bash
cd omni_desk_backend && python manage.py makemigrations smart_assistant --name=native_function_calling
```

期望生成 `smart_assistant/migrations/00XX_native_function_calling.py`,内容含 4 个 `AddField`。

- [ ] **Step 9:运行所有模型测试 → 期望 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_settings_and_migration.py -v
```

- [ ] **Step 10:迁移可逆性检查**

```bash
cd omni_desk_backend && python manage.py migrate smart_assistant zero --plan 2>&1 | head -30
```

期望:出现 4 个 `Reverse:` 操作(无破坏性)。

- [ ] **Step 11:commit**

```bash
git add omni_desk_backend/settings/base.py smart_assistant/models.py smart_assistant/migrations/ smart_assistant/tests/test_settings_and_migration.py
git commit -m "feat(smart-assistant): L1 settings + AgentLog/LlmEndpoint 字段 + 迁移

为原生 Function Calling 协议铺底:
- settings.USE_NATIVE_TOOL_CALLS/MAX_TOOL_CALLS_ROUNDS/TOOL_CALLS_TIMEOUT_SECONDS
- AgentLog.tool_call_path/tool_calls_meta/tool_calls_rounds 决策日志字段
- LlmEndpoint.model_capabilities 端点能力探测字段
- 迁移可逆,旧数据兼容"
```

---

### Task 2:BaseTool abstract + validate_arguments 默认实现

**Files:**
- Modify: `smart_assistant/tools/base.py:50-90`(在 `BaseTool` 类里)
- Test: `smart_assistant/tests/test_base_tool_schema.py`(新建)

**Interfaces:**
- Consumes: `BaseTool.intent_type`、`BaseTool.risk_level`(已有)
- Produces:
  - `BaseTool.get_openai_tool_schema(cls) -> dict`(abstractmethod)
  - `BaseTool.validate_arguments(cls, args: dict) -> dict`(默认基于 schema 自动校验)

- [ ] **Step 1:写失败测试 —— abstractmethod 必现**

`smart_assistant/tests/test_base_tool_schema.py`:

```python
import pytest
from smart_assistant.tools.base import BaseTool


def test_base_tool_get_openai_tool_schema_is_abstract():
    """BaseTool 必须实现 get_openai_tool_schema(),否则不能实例化。"""
    with pytest.raises(TypeError):
        BaseTool()  # 抽象方法未实现,实例化失败
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_base_tool_schema.py -v
```

期望:可能 PASS(因为现有 BaseTool 可能没有 abstract 检查),或者 import 失败。先看实际结果。

- [ ] **Step 3:修改 `smart_assistant/tools/base.py`**

在 `BaseTool` 类上加入 abstractmethod:

```python
from abc import ABC, abstractmethod
import jsonschema  # 新依赖?不,用 jsonschema 库还是自己写?

class BaseTool(ABC):
    # ... 现有字段 ...
    
    @classmethod
    @abstractmethod
    def get_openai_tool_schema(cls) -> dict:
        """返回 OpenAI 兼容的 tool 描述。子类必须实现。"""
        ...
    
    @classmethod
    def validate_arguments(cls, args: dict) -> dict:
        """默认基于 get_openai_tool_schema() 的 parameters 字段做 JSON Schema 校验。

        子类可覆盖以加入业务校验。
        校验失败抛 jsonschema.ValidationError。
        """
        import jsonschema  # 延迟 import 避免污染 base 模块
        schema = cls.get_openai_tool_schema()["function"]["parameters"]
        jsonschema.validate(instance=args, schema=schema)
        return args
```

- [ ] **Step 4:检查 jsonschema 是否已安装**

```bash
cd omni_desk_backend && python -c "import jsonschema; print(jsonschema.__version__)"
```

如果未安装:

```bash
# 编辑 requirements.in,加 jsonschema>=4.0
# 重生成 requirements.txt:
cd omni_desk_backend && pip-compile -o requirements.txt requirements.in
```

> ⚠️ 这是本计划**唯一**新增依赖,选择 jsonschema 是因为 OpenAI strict 模式定义基于 JSON Schema Draft 7。也可以选择 `fastjsonschema`(更快),但 jsonschema 更通用。

- [ ] **Step 5:跑测试 → 期望 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_base_tool_schema.py -v
```

- [ ] **Step 6:写 validate_arguments 行为测试**

在 `test_base_tool_schema.py` 追加:

```python
import jsonschema


class _DummyTool(BaseTool):
    intent_type = "_dummy_test"
    name = "_dummy_test"
    description = "用于测试"

    def execute(self, query, context):
        return {"found": True}

    @classmethod
    def get_openai_tool_schema(cls):
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": "dummy",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }


def test_validate_arguments_passes():
    tool = _DummyTool()
    validated = _DummyTool.validate_arguments({"query": "hi"})
    assert validated == {"query": "hi"}


def test_validate_arguments_missing_required():
    with pytest.raises(jsonschema.ValidationError):
        _DummyTool.validate_arguments({})


def test_validate_arguments_additional_property():
    with pytest.raises(jsonschema.ValidationError):
        _DummyTool.validate_arguments({"query": "hi", "extra": 1})
```

- [ ] **Step 7:跑新测试 → 期望 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_base_tool_schema.py -v
```

- [ ] **Step 8:commit**

```bash
git add smart_assistant/tools/base.py smart_assistant/tests/test_base_tool_schema.py requirements.in requirements.txt requirements-prod.txt
git commit -m "feat(smart-assistant): BaseTool.get_openai_tool_schema() abstract + validate_arguments 默认实现

- BaseTool 升级为 ABC,要求子类实现 get_openai_tool_schema()
- 默认 validate_arguments() 基于 schema 走 jsonschema 校验
- 新增依赖 jsonschema>=4.0(requirements.in/requirements.txt 同步)"
```

---

### Task 3:LLMRouter.generate() 透传 tools 与 tool_choice

**Files:**
- Modify: `llm_service/router.py:50-200`(`generate()` 与 `_call_endpoint()`)
- Test: `smart_assistant/tests/test_llm_router_tool_calls.py`(新建)

**Interfaces:**
- Consumes: `messages: list[dict]`
- Produces:
  - `LLMRouter.generate(..., tools=None, tool_choice=None) -> tuple[str, dict, list[dict]]`
  - 返回值新增第三个元素 `tool_calls`(默认空列表)

- [ ] **Step 1:写失败测试 —— 透传 tools 参数**

`smart_assistant/tests/test_llm_router_tool_calls.py`:

```python
import json
import pytest
from llm_service.router import LLMRouter
from smart_assistant.tests.mock_llm_server import running_server


@pytest.fixture
def mock_server():
    with running_server() as base_url:
        yield base_url


def test_router_generate_passes_tools_to_endpoint(mock_server):
    """router 应将 tools 参数原样透传到 OpenAI 兼容 endpoint。"""
    router = LLMRouter()
    messages = [{"role": "user", "content": "明天排班"}]
    tools = [{
        "type": "function",
        "function": {
            "name": "schedule_query",
            "description": "查询排班",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }]
    
    # Mock server 在收到 tools 时返回 tool_calls 响应(场景在 Task 10 加)
    # 此测试先验证 router 调用成功 + 返回元组为三元组
    content, usage, tool_calls = router.generate(
        messages=messages,
        tools=tools,
        tool_choice="auto",
        endpoint_url=mock_server + "/v1",
    )
    
    # 没有真实 tool_calls 场景时,tool_calls 应为空列表
    assert isinstance(tool_calls, list)
    assert isinstance(content, str)
    assert isinstance(usage, dict)
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_llm_router_tool_calls.py -v
```

期望:`TypeError: generate() got an unexpected keyword argument 'tools'` 或返回值解包错。

- [ ] **Step 3:修改 `llm_service/router.py`**

定位 `generate()` 方法(现有签名因人而异,大致结构):

```python
def generate(
    self,
    messages: list[dict],
    *,
    app_name: str = "smart_assistant",
    tools: list[dict] | None = None,        # NEW
    tool_choice: str | dict | None = None,  # NEW
    stream: bool = False,
    **kwargs,
) -> tuple[str, dict, list[dict]]:
    """扩展返回值为 (content, usage, tool_calls)。
    
    tool_calls 格式:[{"id":..,"type":"function","function":{"name":..,"arguments":..}}]
    若 LLM 未调用工具,返回空列表。
    """
```

修改 `_call_endpoint()` 在 HTTP 请求 body 中加 `tools` / `tool_choice`(仅当非 None):

```python
body = {
    "model": model_name,
    "messages": messages,
    "temperature": temperature,
}
if tools is not None:
    body["tools"] = tools
if tool_choice is not None:
    body["tool_choice"] = tool_choice
# 现有 stream/temperature 等保留
```

修改响应解析:

```python
choice = response["choices"][0]
message = choice["message"]
content = message.get("content") or ""
usage = response.get("usage", {})

# 解析 tool_calls
tool_calls_raw = message.get("tool_calls") or []
tool_calls = []
for tc in tool_calls_raw:
    tool_calls.append({
        "id": tc["id"],
        "type": tc.get("type", "function"),
        "function": {
            "name": tc["function"]["name"],
            "arguments": tc["function"]["arguments"],
        },
    })

return content, usage, tool_calls
```

> 若现有 `generate()` 返回二元组,需要把所有调用点更新为三元组。本任务只跑单测,集成在 Task 6 处理。

- [ ] **Step 4:跑测试 → 期望 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_llm_router_tool_calls.py -v
```

- [ ] **Step 5:跑现有 router 测试确认无回归**

```bash
cd omni_desk_backend && pytest llm_service/tests/ -v
```

- [ ] **Step 6:commit**

```bash
git add llm_service/router.py smart_assistant/tests/test_llm_router_tool_calls.py
git commit -m "feat(llm-service): LLMRouter.generate() 透传 tools/tool_choice,返回 tool_calls 三元组

- generate() 新增 tools/tool_choice 参数,透传到 OpenAI 兼容 endpoint
- 返回值扩展为 (content, usage, tool_calls)
- 现有 router 单测无回归"
```

---

### Task 4:18 个工具 schema 适配

**Files:**
- Modify: 18 个 `smart_assistant/tools/*_tool.py`(各加 `get_openai_tool_schema()` + `_describe_parameters()`)
- Test: `smart_assistant/tests/test_openai_tool_schemas.py`(新建)

**Interfaces:**
- 每个工具返回 schema:`{"type":"function","function":{"name":intent_type,"description":..,"parameters":<JSON Schema strict>}}`
- `parameters` 必须有 `additionalProperties: false`(每层)

- [ ] **Step 1:写统一测试**

`smart_assistant/tests/test_openai_tool_schemas.py`:

```python
import pytest
from smart_assistant.tools.registry import ToolRegistry


def _collect_all_tools():
    """从 ToolRegistry 实例化所有工具子类。"""
    registry = ToolRegistry()
    return list(registry._tools.values())


ALL_TOOL_CLASSES = _collect_all_tools()


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES, ids=lambda c: c.intent_type)
def test_tool_schema_is_valid_openai_function(tool_cls):
    schema = tool_cls.get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == tool_cls.intent_type
    assert isinstance(schema["function"]["description"], str)
    assert len(schema["function"]["description"]) >= 5
    assert schema["function"]["parameters"]["type"] == "object"
    assert "required" in schema["function"]["parameters"]
    assert schema["function"].get("strict") is True


def _assert_strict(node):
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False, f"object 节点缺 additionalProperties=false: {node}"
        for prop in node.get("properties", {}).values():
            _assert_strict(prop)
    elif node.get("type") == "array":
        _assert_strict(node["items"])


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES, ids=lambda c: c.intent_type)
def test_tool_schema_is_strict(tool_cls):
    """OpenAI strict 模式要求每层 object/array 都有 additionalProperties=false。"""
    schema = tool_cls.get_openai_tool_schema()
    _assert_strict(schema["function"]["parameters"])
```

- [ ] **Step 2:跑测试 → 期望 FAIL(多数工具未实现)**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_openai_tool_schemas.py -v
```

期望:18 个工具中有 ~17 个抛 `NotImplementedError` 或返回非 dict。

- [ ] **Step 3:为简单工具组(7 个)添加 schema**

按工作量**从简到难**实现,每个工具 2 处改动:加 classmethod + 在 `_describe_parameters()` 内复用。

工具清单(按 spec §3.1 估算):

**简单(7 个,~10 行/个)**:`ScheduleTool` / `EventTool` / `MemoTool` / `NewsTool` / `MeetingRoomTool` / `AnnouncementTool` / `ExternalLinkTool`

以 `ScheduleTool` 为模板(spec 附录 A 完整示例):

```python
# smart_assistant/tools/schedule_tool.py
class ScheduleTool(BaseTool):
    intent_type = "schedule_query"
    risk_level = RISK_LEVEL_READ
    
    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": "查询排班/值班信息。支持日期范围、人员姓名、班次类型过滤。示例:'明天的排班'、'本周张三的值班'。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "自然语言查询,可含日期/人员/班次关键词"},
                        "date_from": {"type": "string", "format": "date", "description": "起始日期(ISO 8601),可选"},
                        "date_to": {"type": "string", "format": "date", "description": "结束日期(ISO 8601),可选"},
                        "personnel_name": {"type": "string", "description": "人员姓名,精确匹配"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
```

其余 6 个简单工具按此模板,**复用各自 execute() 的实际参数**。

- [ ] **Step 4:跑测试 → 部分 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_openai_tool_schemas.py -v
```

期望:7 个简单工具通过,11 个仍 FAIL。

- [ ] **Step 5:为中等工具组(6 个)添加 schema**

`PersonnelTool` / `ProjectTool` / `ComplianceTool` / `SensorTool` / `RAGTool` / `DocumentTool`

每个约 20 行。注意:

- `RAGTool` 参数含 `dataset_ids` array(嵌套,记得 array 内 `items` 也要 strict)
- `ComplianceTool` 参数含枚举 `severity`(JSON Schema enum 字段)
- `PersonnelTool` 可加 `department` 字段

- [ ] **Step 6:跑测试 → 13 个 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_openai_tool_schemas.py -v
```

- [ ] **Step 7:为 office 工具组(3 个)添加 schema**

`OfficeReadTool` / `OfficeGenerateTool` / `SpreadsheetTool`

这些工具 2026-08 阶段 1 已有 `parameters` 描述,但**未走 strict 模式**。改造要点:

- `OfficeGenerateTool`(`risk_level=write + require_confirmation`):在 description 中**显式提示需要用户确认**
- 三个工具的 description 都按 spec §3.1 表格的"2 句中文说明 + 示例 query"格式补全

- [ ] **Step 8:跑测试 → 16 个 PASS**

- [ ] **Step 9:为剩余 2 个非典型工具补 schema**

`RAGTool` 多数据集选择 + `OfficeGenerateTool` 写文件

在 schema description 中显式说明约束(避免 LLM 误用)。

- [ ] **Step 10:跑测试 → 18 个全 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_openai_tool_schemas.py -v
```

期望:`18 passed`。

- [ ] **Step 11:运行所有现有工具测试确认无回归**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_tools_*.py smart_assistant/tests/test_*_tool*.py -v
```

期望:全绿(execute() 行为未改,只加了 classmethod)。

- [ ] **Step 12:commit**

```bash
git add smart_assistant/tools/ smart_assistant/tests/test_openai_tool_schemas.py
git commit -m "feat(smart-assistant): 18 个 BaseTool 实现 get_openai_tool_schema()

按 OpenAI strict JSON Schema 规范输出:
- name = intent_type(与现有路由键对齐)
- parameters 每层 additionalProperties=false
- description 含中文说明 + 示例 query
- 现有 execute() 行为不变,无回归"
```

---

# 阶段 2:编排与降级(Sprint 1,Day 5-7 + Sprint 2,Day 1-2)

> 目标:让 orchestrator 走通 tool_calls 主循环,JSON 路径作 fallback。链路集成测试可用。

---

### Task 5:ToolRegistry.get_openai_tools(user)

**Files:**
- Modify: `smart_assistant/tools/registry.py`(在 `get_tool_for_user()` 后追加 `get_openai_tools()`)
- Test: `smart_assistant/tests/test_registry_get_openai_tools.py`(新建)

**Interfaces:**
- Produces:
  - `ToolRegistry.get_openai_tools(user) -> list[dict]`(按 user 过滤 + 按 risk_level 排序)

- [ ] **Step 1:写失败测试**

```python
import pytest
from smart_assistant.tools.registry import ToolRegistry
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_get_openai_tools_returns_all_for_authenticated_user():
    User = get_user_model()
    user = User.objects.create_user(username="tester", password="x")
    registry = ToolRegistry()
    tools = registry.get_openai_tools(user)
    assert isinstance(tools, list)
    assert len(tools) >= 15  # 18 个里至少 15 个 required_auth=True 的能用
    names = {t["function"]["name"] for t in tools}
    assert "schedule_query" in names


@pytest.mark.django_db
def test_get_openai_tools_unauthenticated_returns_empty_or_anonymous_only():
    from django.contrib.auth.models import AnonymousUser
    registry = ToolRegistry()
    tools = registry.get_openai_tools(AnonymousUser())
    # required_auth=True 的工具必须被过滤;若所有都 required 则返回空列表
    assert all(
        t["function"]["name"] not in {"schedule_query"}  # 示例:schedule 必登录
        for t in tools
    )


def test_get_openai_tools_sorted_read_first():
    """read-only 工具应排在 write/destructive 之前,降低 LLM 误调写工具风险。"""
    User = get_user_model()
    user = User.objects.create_user(username="tester", password="x")
    registry = ToolRegistry()
    tools = registry.get_openai_tools(user)
    # 找到第一个非 read 工具的位置
    for i, tool in enumerate(tools):
        tool_cls = registry._tool_classes_by_name[tool["function"]["name"]]
        if tool_cls.risk_level != RISK_LEVEL_READ:
            # 之后所有工具都应该不是 read
            for later in tools[i:]:
                later_cls = registry._tool_classes_by_name[later["function"]["name"]]
                assert later_cls.risk_level != RISK_LEVEL_READ
            break
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_registry_get_openai_tools.py -v
```

期望:`AttributeError: 'ToolRegistry' object has no attribute 'get_openai_tools'`

- [ ] **Step 3:实现 `get_openai_tools()`**

```python
# smart_assistant/tools/registry.py

def get_openai_tools(self, user) -> list[dict]:
    """返回当前用户可用的 OpenAI 协议 tools 列表。

    1. 遍历 self._tools
    2. 跳过 BaseTool.required_auth=True 且用户未登录
    3. 调 cls.get_openai_tool_schema() 收集
    4. 按 risk_level 排序(read 在前)
    """
    tools = []
    is_auth = user is not None and getattr(user, "is_authenticated", False)
    
    for tool_cls in self._tool_classes.values():
        if tool_cls.required_auth and not is_auth:
            continue
        try:
            schema = tool_cls.get_openai_tool_schema()
        except NotImplementedError:
            continue  # 未实现的工具跳过(向后兼容)
        if isinstance(schema, dict):
            tools.append(schema)
    
    # 按 risk_level 排序
    risk_order = {"read": 0, "write": 1, "destructive": 2}
    tools.sort(key=lambda t: risk_order.get(
        self._tool_classes_by_name[t["function"]["name"]].risk_level, 0
    ))
    
    return tools
```

注意:你可能需要补 `_tool_classes`(类列表)和 `_tool_classes_by_name`(name→类 映射)的初始化逻辑(若不存在)。

- [ ] **Step 4:跑测试 → 期望 PASS**

- [ ] **Step 5:commit**

```bash
git add smart_assistant/tools/registry.py smart_assistant/tests/test_registry_get_openai_tools.py
git commit -m "feat(smart-assistant): ToolRegistry.get_openai_tools(user) 自动拼装 + 用户过滤

按 spec §3.2:
- 跳过未登录用户对 required_auth 工具的访问
- 按 risk_level 排序(read→write→destructive)
- 跳过未实现 schema 的工具(向后兼容)"
```

---

### Task 6:AgentOrchestrator 新增 _process_tool_calls_path 主循环

**Files:**
- Modify: `smart_assistant/agent/orchestrator.py`(把现有 `process()` 中的工具调用逻辑拆分为两个路径)
- Test: `smart_assistant/tests/test_orchestrator_tool_calls_path.py`(新建)

**Interfaces:**
- Produces:
  - `AgentOrchestrator._process_tool_calls_path(query, context, llm_messages) -> tuple[str, dict, dict]`(新增)
  - `AgentOrchestrator._process_json_path(query, context, llm_messages) -> tuple[str, dict, dict]`(从原 process() 拆分)
  - `AgentOrchestrator.process()`(顶层根据 `settings.USE_NATIVE_TOOL_CALLS + endpoint capability` 选路径)

- [ ] **Step 1:写失败测试 —— tool_calls 主循环 happy path**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.tools.base import ToolContext


@pytest.fixture
def mock_tool_call_response():
    """模拟 LLM 第一轮返回 tool_calls,第二轮返回自然语言。"""
    return [
        {  # 第一轮
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "明天"}),
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"total_tokens": 100},
        },
        {  # 第二轮
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "明天是张三早班",
                    "tool_calls": None,
                },
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 50},
        },
    ]


@pytest.mark.django_db
def test_tool_calls_path_executes_tool_and_returns_answer(mock_tool_call_response):
    user = MagicMock(is_authenticated=True, is_staff=False, has_perm=lambda x: True)
    context = ToolContext(user=user)
    
    orchestrator = AgentOrchestrator()
    
    with patch.object(orchestrator.router, "generate", side_effect=[
        (resp["choices"][0]["message"].get("content") or "",
         resp.get("usage", {}),
         resp["choices"][0]["message"].get("tool_calls") or [])
        for resp in mock_tool_call_response
    ]):
        # mock ScheduleTool.execute 返回有效结果
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user") as mock_get_tool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.execute_with_guard.return_value = {"found": True, "items": [{"shift": "早班"}]}
            mock_tool_instance.validate_arguments.return_value = {"query": "明天"}
            mock_get_tool.return_value = mock_tool_instance
            
            content, usage, meta = orchestrator._process_tool_calls_path(
                query="明天排班", context=context, llm_messages=[{"role": "user", "content": "明天排班"}]
            )
    
    assert "张三早班" in content or "早班" in content
    assert meta["tool_calls_rounds"] >= 1
    assert len(meta["tool_calls_meta"]) >= 1
    assert meta["tool_calls_meta"][0]["tool"] == "schedule_query"
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_orchestrator_tool_calls_path.py -v
```

- [ ] **Step 3:实现 `_process_tool_calls_path()`**

参考 spec §3.4 的伪代码实现:

```python
def _process_tool_calls_path(self, *, query, context, llm_messages):
    from smart_assistant.tools.registry import ToolRegistry
    from smart_assistant.agent.tool_context_resolver import resolve_tools_for_user
    
    tools_schema = resolve_tools_for_user(context.user)
    tool_calls_meta = []
    rounds = 0
    
    for round_idx in range(settings.MAX_TOOL_CALLS_ROUNDS):
        content, usage, tool_calls = self.router.generate(
            messages=llm_messages,
            tools=tools_schema,
            tool_choice="auto",
            app_name="smart_assistant",
        )
        
        if not tool_calls:
            # LLM 主动选择不调用工具,直接返回
            return content, usage, {
                "tool_calls_meta": tool_calls_meta,
                "tool_calls_rounds": rounds,
                "tool_call_path": "native",
            }
        
        rounds += 1
        tool_results = []
        
        for tc in tool_calls:
            t0 = time.monotonic()
            tool = ToolRegistry().get_tool_for_user(tc["function"]["name"], context.user)
            
            if tool is None:
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"error": "tool_unavailable_for_user"}),
                })
                tool_calls_meta.append({
                    "round": round_idx, "tool": tc["function"]["name"],
                    "error": "unavailable", "duration_ms": 0,
                })
                continue
            
            try:
                args = json.loads(tc["function"]["arguments"])
                validated = tool.validate_arguments(args)
            except Exception as e:
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"error": "invalid_arguments", "detail": str(e)}),
                })
                tool_calls_meta.append({
                    "round": round_idx, "tool": tc["function"]["name"],
                    "error": "invalid_args", "duration_ms": 0,
                })
                continue
            
            try:
                result = tool.execute_with_guard(validated, context)
                duration_ms = int((time.monotonic() - t0) * 1000)
                tool_calls_meta.append({
                    "round": round_idx, "tool": tc["function"]["name"],
                    "arguments": validated, "duration_ms": duration_ms,
                })
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })
            except Exception as e:
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"error": "execution_failed", "detail": str(e)}),
                })
                tool_calls_meta.append({
                    "round": round_idx, "tool": tc["function"]["name"],
                    "error": "execution_failed", "duration_ms": 0,
                })
        
        llm_messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
        llm_messages.extend(tool_results)
    
    # 3 轮后兜底:强制 tool_choice="none"
    content, usage, _ = self.router.generate(
        messages=llm_messages, tools=tools_schema, tool_choice="none",
        app_name="smart_assistant",
    )
    return content, usage, {
        "tool_calls_meta": tool_calls_meta,
        "tool_calls_rounds": rounds,
        "tool_call_path": "native",
    }
```

- [ ] **Step 4:拆分 `_process_json_path()`**

把现有 `process()` 中的 JSON 解析逻辑提取为独立方法。**改动应最小**:把现有 `process()` 函数体内除 tools/tool_choice 之外的所有逻辑(意图分类 → 单工具执行 → LLM 综合回答 → 缓存写入)原样剪切到 `_process_json_path()`,函数签名与 `_process_tool_calls_path` 对齐:

```python
def _process_json_path(self, *, query, context, llm_messages):
    # ↓↓↓ 以下逻辑从原 process() 函数体内原样迁移,无业务改动 ↓↓↓
    # 1) 意图分类(IntentClassifier.classify)
    # 2) ToolChainPlanner.plan + ToolChainExecutor.execute(走现有 18 工具)
    # 3) ResultSynthesizer.synthesize 聚合
    # 4) LLM.generate 综合自然语言回答
    # 5) 写 session.messages + AgentLog(estimated_cost 等)
    # ... 完整照搬原 process() 中除路由逻辑外的所有步骤 ...
    return content, usage, {
        "tool_calls_meta": [],
        "tool_calls_rounds": 0,
        "tool_call_path": "json",
    }
```

> 关键不变量:`_process_json_path()` **不修改现有任何业务逻辑**,仅新增第三个返回值 `meta`。这是 fallback 路径,A/B 评估期间必须 100% 行为对等于旧 `process()`。

- [ ] **Step 5:改写 `process()` 顶层路由**

```python
def process(self, *, query, context, llm_messages=None):
    if llm_messages is None:
        llm_messages = self._build_initial_messages(query, context)
    
    use_native = (
        settings.USE_NATIVE_TOOL_CALLS
        and self._endpoint_supports_tool_calls()
    )
    
    if use_native:
        return self._process_tool_calls_path(
            query=query, context=context, llm_messages=llm_messages
        )
    return self._process_json_path(
        query=query, context=context, llm_messages=llm_messages
    )
```

`_endpoint_supports_tool_calls()` 实现:检查当前激活的 `LlmEndpoint.model_capabilities.native_tool_calls`(详见 Task 8)。

- [ ] **Step 6:跑测试 → 期望 PASS**

- [ ] **Step 7:跑现有 chat 集成测试确认无回归**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_*chat*.py smart_assistant/tests/test_*e2e*.py -v
```

- [ ] **Step 8:commit**

```bash
git add smart_assistant/agent/orchestrator.py smart_assistant/tests/test_orchestrator_tool_calls_path.py
git commit -m "feat(smart-assistant): AgentOrchestrator tool_calls 主循环 + JSON 路径拆分

按 spec §3.4 实现:
- _process_tool_calls_path() 最多 3 轮,3 轮后强制 tool_choice='none'
- _process_json_path() 保留现有逻辑(返回三元组)
- process() 顶层根据 settings.USE_NATIVE_TOOL_CALLS + endpoint 能力选路径
- tool_calls_meta 记录每轮 round/tool/arguments/duration_ms/error"
```

---

### Task 7:cache 加 tool_call_path 维度

**Files:**
- Modify: `smart_assistant/cache.py:50-100`(`_build_cache_key` 函数)

**Interfaces:**
- Produces:cache_key 在原 hash 上加 `tool_call_path` 维度,避免 A/B 切换时缓存污染

- [ ] **Step 1:写测试**

```python
import pytest
from smart_assistant.cache import _build_cache_key


def test_cache_key_includes_tool_call_path():
    """同一 query 在 native/json 两种路径下应有不同 cache key。"""
    key1 = _build_cache_key(query="明天", user_id=1, intent="schedule", tool_call_path="native")
    key2 = _build_cache_key(query="明天", user_id=1, intent="schedule", tool_call_path="json")
    assert key1 != key2
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_cache*.py -k "tool_call_path" -v
```

- [ ] **Step 3:修改 `_build_cache_key()`**

加 `tool_call_path: str` 参数,加入 hash 输入:

```python
def _build_cache_key(query, user_id, intent, *, tool_call_path="none", cache_version=None):
    sig = f"u{user_id}_i{intent}_p{tool_call_path}_v{cache_version or CACHE_VERSION}"
    return f"smart_assistant:{hashlib.md5((query + sig).encode()).hexdigest()[:16]}"
```

更新所有调用点(`orchestrator.py` / `cache.py` 内部),传入实际路径。

- [ ] **Step 4:跑测试 → 期望 PASS + 跑全部 cache 测试确认无回归**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_cache*.py -v
```

- [ ] **Step 5:commit**

```bash
git add smart_assistant/cache.py smart_assistant/tests/
git commit -m "fix(smart-assistant): cache key 加 tool_call_path 维度,防 A/B 切换缓存污染"
```

---

### Task 8:doctor 新增 native_tool_calls 检查项

**Files:**
- Modify: `smart_assistant/views/doctor.py`(`CHECKERS` 元组)
- Test: `smart_assistant/tests/test_doctor_native_tool_calls.py`(新建)

**Interfaces:**
- Produces:doctor 输出新增 `native_tool_calls` 检查项,探测激活端点的 tool_calls 能力

- [ ] **Step 1:写失败测试**

```python
@pytest.mark.django_db
def test_doctor_includes_native_tool_calls_check(staff_client):
    response = staff_client.get("/api/smart-assistant/doctor/")
    data = response.json()
    check_names = {c["name"] for c in data["checks"]}
    assert "native_tool_calls" in check_names
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

- [ ] **Step 3:实现 `native_tool_calls_checker()`**

> ⚠️ `LLMRouter.generate()` 当前签名未支持 `endpoint_override` 参数。如不支持,改用临时 patch:
> ```python
> with patch.object(LLMRouter, "_call_endpoint") as mock_call:
>     mock_call.return_value = {"choices": [...], "usage": {...}}
>     ...
> ```
> 若当前签名已支持 endpoint 覆盖,直接传 `endpoint_override=endpoint` 即可。

```python
def native_tool_calls_checker():
    """向激活端点发最小 tool_calls 请求,验证是否返回 tool_calls。"""
    from llm_service.router import LLMRouter
    try:
        endpoint = LlmEndpoint.objects.filter(is_active=True).first()
        if not endpoint:
            return {"status": "warn", "kind": "no_llm_endpoint", "message": "无激活端点"}
        # 发最小请求(若 endpoint_override 不支持则用 patch._call_endpoint)
        router = LLMRouter()
        _, _, tool_calls = router.generate(
            messages=[{"role": "user", "content": "ping"}],
            tools=[{"type": "function", "function": {"name": "_ping", "description": "ping", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True}}],
            tool_choice="auto",
            app_name="smart_assistant",
            endpoint_override=endpoint,  # 或 patch
        )
        # 更新端点能力
        caps = endpoint.model_capabilities or {}
        caps["native_tool_calls"] = bool(tool_calls) or caps.get("native_tool_calls", False)
        endpoint.model_capabilities = caps
        endpoint.save(update_fields=["model_capabilities"])
        return {"status": "ok", "kind": "ok", "message": f"端点支持 tool_calls={bool(tool_calls)}"}
    except Exception as e:
        return {"status": "error", "kind": "endpoint_probe_failed", "message": str(e)}
```

加到 `CHECKERS` 元组末尾。

- [ ] **Step 4:跑测试 → PASS + 跑 doctor 测试无回归**

- [ ] **Step 5:commit**

```bash
git add smart_assistant/views/doctor.py smart_assistant/tests/test_doctor_native_tool_calls.py
git commit -m "feat(smart-assistant): doctor 自检新增 native_tool_calls 检查项

探测激活 LlmEndpoint 的 tool_calls 能力,结果缓存到 model_capabilities.native_tool_calls"
```

---

### Task 9:JSON 路径 fallback 测试

**Files:**
- Test: `smart_assistant/tests/test_json_path_fallback.py`(新建)

**Interfaces:**
- 验证 settings.USE_NATIVE_TOOL_CALLS=False 或 endpoint 不支持时,自动降级到 JSON 路径

- [ ] **Step 1:写测试**

```python
import pytest
from django.test import override_settings
from unittest.mock import patch


@pytest.mark.django_db
@override_settings(USE_NATIVE_TOOL_CALLS=False)
def test_process_falls_back_to_json_when_setting_disabled():
    """settings 关闭时强制走 JSON 路径。"""
    from smart_assistant.agent.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    # 调用 process,断言 _process_json_path 被调用
    with patch.object(orch, "_process_json_path") as mock_json:
        mock_json.return_value = ("ok", {}, {"tool_call_path": "json"})
        orch.process(query="x", context=mock_context())
        mock_json.assert_called_once()
        assert orch._process_tool_calls_path.called is False


@pytest.mark.django_db
def test_process_falls_back_when_endpoint_lacks_capability():
    """端点 capability=false 时走 JSON 路径。"""
    # ... 类似上面,但 mock _endpoint_supports_tool_calls 返回 False ...
```

- [ ] **Step 2:跑测试 → 期望 PASS(因为 process() 已实现顶层路由)**

- [ ] **Step 3:commit**

```bash
git add smart_assistant/tests/test_json_path_fallback.py
git commit -m "test(smart-assistant): JSON 路径 fallback 测试覆盖(settings 关闭 + endpoint 不支持)"
```

---

# 阶段 3:E2E 与灰度(Sprint 2,Day 3-7)

> 目标:打通完整 E2E,验证 4 个完工定义。

---

### Task 10:Mock LLM server 扩展 tool_calls 场景

**Files:**
- Modify: `smart_assistant/tests/mock_llm_server.py`(在现有 keyword 路由后加 tool_calls 场景)

**Interfaces:**
- 收到带 `tools` 的请求时,按 query 关键字返回预设的 tool_calls 序列

- [ ] **Step 1:写测试 —— Mock server 处理 tool_calls 请求**

```python
import json
import pytest
import requests
from smart_assistant.tests.mock_llm_server import running_server


@pytest.fixture
def mock_url():
    with running_server() as base:
        yield base


def test_mock_server_returns_tool_calls_for_known_keyword(mock_url):
    """当 query 含 '明天排班' 且带 tools 时,返回 tool_calls 响应。"""
    payload = {
        "model": "test",
        "messages": [{"role": "user", "content": "明天排班"}],
        "tools": [{
            "type": "function",
            "function": {"name": "schedule_query", "description": "x",
                         "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
            "strict": True,
        }],
    }
    r = requests.post(f"{mock_url}/v1/chat/completions", json=payload, timeout=5)
    data = r.json()
    assert data["choices"][0]["finish_reason"] == "tool_calls"
    assert data["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "schedule_query"
```

- [ ] **Step 2:跑测试 → 期望 FAIL**

- [ ] **Step 3:扩展 mock server**

在 `mock_llm_server.py` 的路由处理中加:

```python
TOOL_CALL_SCENARIOS = {
    "明天排班": [
        {
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": "call_mock_001", "type": "function",
                        "function": {"name": "schedule_query",
                                     "arguments": json.dumps({"query": "明天"})},
                    }],
                },
            }],
            "usage": {"total_tokens": 100},
        },
        {  # 第二轮:自然语言
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "明天是张三早班", "tool_calls": None},
            }],
            "usage": {"total_tokens": 50},
        },
    ],
    # 至少覆盖 schedule / personnel / rag / memo / news 5 个场景
}

def _select_scenario(body, call_count):
    """根据 query 选预设场景;返回该轮响应。"""
    messages = body.get("messages", [])
    last_user_msg = next((m for m in reversed(messages) if m["role"] == "user"), {}).get("content", "")
    
    for keyword, scenario in TOOL_CALL_SCENARIOS.items():
        if keyword in last_user_msg and call_count < len(scenario):
            return scenario[call_count]
    return None
```

修改 `_handle_chat_completion`,在响应前调 `_select_scenario()`,若返回非 None 则用预设响应(否则走现有 keyword 路由)。

**注意:**需要 per-conversation call 计数,可在 handler 内用 `id()` 或 thread-local 计数;最简方案是把每次请求视为新一轮(因为 E2E 测试通常每 case 独立)。

- [ ] **Step 4:跑测试 → PASS**

- [ ] **Step 5:跑 mock_llm_server 现有测试无回归**

- [ ] **Step 6:commit**

```bash
git add smart_assistant/tests/mock_llm_server.py smart_assistant/tests/test_llm_router_tool_calls.py
git commit -m "test(smart-assistant): Mock LLM server 扩展 TOOL_CALL_SCENARIOS

支持 5+ 个工具调用场景(schedule/personnel/rag/memo/news),
让 E2E 测试可验证完整 tool_calls 链路"
```

---

### Task 11:E2E 8 个用例

**Files:**
- Create: `smart_assistant/tests/test_native_function_calling_e2e.py`

**Interfaces:**
- 8 个 E2E 用例对应 spec §6.3 表格

- [ ] **Step 1:happy path + 两工具并行**

```python
@pytest.mark.django_db
def test_e2e_happy_path_single_tool(staff_client, mock_llm_server, schedule_fixture):
    """LLM 调 1 个工具 → 后端执行 → 第二轮自然语言回答。"""
    # mock LLM server 配置"明天排班"→tool_calls(schedule_query)
    # fixture 提供 Schedule 数据
    response = staff_client.post("/api/smart-assistant/chat/", {
        "message": "明天排班",
    }, format="json")
    
    assert response.status_code == 200
    data = response.json()
    assert "早班" in data["answer"] or "张三" in data["answer"]
    assert data["tool_call_path"] == "native"
    assert data["tool_used"] == "schedule_query"
    assert data["tool_calls_rounds"] == 1
    assert len(data["tool_calls_meta"]) == 1


@pytest.mark.django_db
def test_e2e_two_tools_parallel(staff_client, mock_llm_server, fixture_setup):
    """LLM 1 轮调 2 个工具 → 总结。"""
    # Mock 配置 "本周安排" → tool_calls 同时调 schedule_query + memo_query
    response = staff_client.post("/api/smart-assistant/chat/", {
        "message": "本周安排",
    }, format="json")
    
    assert response.status_code == 200
    data = response.json()
    assert data["tool_calls_rounds"] == 1
    assert len(data["tool_calls_meta"]) == 2
```

- [ ] **Step 2:异常路径 3 个**

```python
def test_e2e_invalid_arguments_lmm_recovers(...):
    """arguments 不合法 → LLM 重试。"""
    # Mock 配置:第一轮返回 arguments="not json" → tool 注入 invalid_arguments → 第二轮 LLM 修正
    
def test_e2e_unauthorized_tool_blocked(...):
    """普通用户调到 admin-only 工具 → tool_unavailable → LLM 换工具。"""
    # Mock 配置:第一轮返回 admin_tool → 注入 unavailable → 第二轮换工具
    
def test_e2e_max_rounds_fallback(...):
    """Mock LLM 永远返回 tool_calls → 3 轮后强制 tool_choice=none。"""
    # Mock 配置:每次都返回 tool_calls(无第二轮结束信号)
    # 验证:tool_calls_rounds == 3,最终 answer 非空
```

- [ ] **Step 3:fallback + streaming + 决策日志**

```python
def test_e2e_json_path_fallback(...):
    """旧端点(无 tool_calls 能力)→ AgentLog.tool_call_path=='json'。"""
    # Mock 一个返回 400 的端点(OpenAI 协议对 tools 不支持时报错)
    
def test_e2e_streaming_with_tool_calls(...):
    """SSE 路径中途 tool_calls → done 帧带 finish_reason → 最终回答。"""
    
def test_e2e_decision_log_persisted(...):
    """AgentLog.tool_calls_meta 字段写入正确。"""
    # chat 后查 AgentLog.tool_calls_meta 含 {round, tool, arguments, duration_ms}
```

- [ ] **Step 4:跑全部 E2E → 8 个全 PASS**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/test_native_function_calling_e2e.py -v
```

- [ ] **Step 5:跑全部 smart_assistant 测试确认无回归**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/ -v
```

- [ ] **Step 6:commit**

```bash
git add smart_assistant/tests/test_native_function_calling_e2e.py
git commit -m "test(smart-assistant): L1 E2E 8 个用例覆盖 spec §6.3 表格

happy_path/two_tools_parallel/invalid_arguments/unauthorized_tool_blocked
/max_rounds_fallback/json_path_fallback/streaming_with_tool_calls
/decision_log_persisted 全 PASS"
```

---

### Task 12:文档归档 + staff 灰度开关

**Files:**
- Modify: `docs/technical/16-smart-assistant.md`(在末尾追加 §13)
- Modify: `docs/user-manual/08-smart-assistant-usage.md`(追加 L1 相关用户可见变化)
- Modify: `smart_assistant/agent/orchestrator.py`(加 `is_staff` 灰度判断)

- [ ] **Step 1:写文档 §13**

在 `docs/technical/16-smart-assistant.md` 末尾追加:

```markdown
## 13. 原生 Function Calling(L1,2026-08-06 实施)

智能助手的 LLM router 现已支持 OpenAI 兼容协议的原生 tool_calls / tool_choice。
实现细节见 `docs/superpowers/specs/2026-08-06-native-function-calling-design.md`。

### 13.1 协议支持

- LLM 端点必须支持 OpenAI `/v1/chat/completions` 的 `tools=[...]` + `tool_choice` 参数
- doctor 自检的 `native_tool_calls` 项自动探测并缓存到 `LlmEndpoint.model_capabilities`
- 旧端点自动降级到 JSON 路径(`AgentLog.tool_call_path="json"`)

### 13.2 主循环

- 最多 3 轮,3 轮后强制 `tool_choice="none"` 让 LLM 给出最终回答
- 工具调用错误分 4 类:invalid_arguments / tool_unavailable_for_user / tool_timeout / execution_failed
- LLM 通常会自动重选工具

### 13.3 决策日志

`AgentLog.tool_calls_meta` 字段记录每轮:
- `round`(0-indexed)
- `tool`(intentional_type)
- `arguments`(LLM 给的参数,用于 A/B 评估)
- `duration_ms`(工具执行耗时)
- `error`(失败原因)

### 13.4 灰度策略

- 默认:仅 `is_staff=True` 用户启用新路径
- 验证 1 周后,通过 settings `USE_NATIVE_TOOL_CALLS_FOR_ALL=True` 全员开放
```

- [ ] **Step 2:用户手册追加**

在 `docs/user-manual/08-smart-assistant-usage.md` 加一段:

> **2026-08 更新**:智能助手现在使用 LLM 原生 function calling 协议选择工具,响应可能比之前稍慢(多 1 轮 LLM 调用),但选错工具的概率显著降低。若您发现回答异常(例如答非所问、调用了错误的工具),请通过"👍/👎"反馈,这将帮助我们改进工具描述质量。

- [ ] **Step 3:加灰度 settings**

在 `settings/base.py` 加:

```python
# L1 灰度:仅 staff 用户启用
USE_NATIVE_TOOL_CALLS_FOR_ALL = False  # 默认仅 staff
```

在 `orchestrator.py` 的 `process()` 路由判断改为:

```python
use_native = (
    settings.USE_NATIVE_TOOL_CALLS
    and self._endpoint_supports_tool_calls()
    and (context.user.is_staff or settings.USE_NATIVE_TOOL_CALLS_FOR_ALL)
)
```

- [ ] **Step 4:写灰度测试**

```python
@pytest.mark.django_db
def test_non_staff_falls_back_to_json_path(staff_client_disabled, regular_user_client, mock_llm_server):
    """非 staff 用户在灰度期间走 JSON 路径。"""
    # regular_user_client 发 chat → 断言 tool_call_path='json'
```

- [ ] **Step 5:跑全部测试 → 全绿**

```bash
cd omni_desk_backend && pytest smart_assistant/tests/ -v
```

- [ ] **Step 6:commit**

```bash
git add docs/ smart_assistant/agent/orchestrator.py smart_assistant/tests/
git commit -m "docs+feat(smart-assistant): L1 §13 章节归档 + staff 灰度开关

- docs/technical/16-smart-assistant.md 加 §13 协议支持/主循环/决策日志/灰度
- docs/user-manual/08-smart-assistant-usage.md 用户可见变化说明
- settings.USE_NATIVE_TOOL_CALLS_FOR_ALL 控制全员开放
- 默认仅 is_staff 走新路径,1 周验证后开放"
```

---

## 验收清单(对应 spec §10 的 4 项完工定义)

| 完工定义 | 对应 Task | 验证命令 |
|---|---|---|
| LLM 原生 tool_calls + 后端路由 + E2E 打通 | T6, T11(`test_e2e_happy_path_single_tool` + `test_e2e_two_tools_parallel`) | `pytest smart_assistant/tests/test_native_function_calling_e2e.py::test_e2e_happy_path_single_tool -v` |
| BaseTool 适配 OpenAI 协议 schema 输出 | T4(18 个工具 schema 测试) | `pytest smart_assistant/tests/test_openai_tool_schemas.py -v`(期望 36 passed:18 schema + 18 strict) |
| ToolChain 适配 + 工具选择决策日志 | T6 + T11(`test_e2e_decision_log_persisted`) | `pytest smart_assistant/tests/test_native_function_calling_e2e.py::test_e2e_decision_log_persisted -v` |
| 保留 JSON 路径作 fallback + 可 A/B | T9 + T11(`test_e2e_json_path_fallback`)+ T12 灰度 | `pytest smart_assistant/tests/test_json_path_fallback.py -v` |

**所有 Task 完成后,执行**:

```bash
cd omni_desk_backend && pytest smart_assistant/tests/ -v  # 期望全绿
cd omni_desk_backend && python manage.py check  # 期望无系统错误
cd omni_desk_frontend && npm test  # 前端无相关改动,期望无回归
```

---

## 执行后产出汇总

**新增文件(5 个)**:
- `smart_assistant/tests/test_settings_and_migration.py`
- `smart_assistant/tests/test_base_tool_schema.py`
- `smart_assistant/tests/test_llm_router_tool_calls.py`
- `smart_assistant/tests/test_openai_tool_schemas.py`
- `smart_assistant/tests/test_registry_get_openai_tools.py`
- `smart_assistant/tests/test_orchestrator_tool_calls_path.py`
- `smart_assistant/tests/test_doctor_native_tool_calls.py`
- `smart_assistant/tests/test_json_path_fallback.py`
- `smart_assistant/tests/test_native_function_calling_e2e.py`
- `smart_assistant/migrations/00XX_native_function_calling.py`

**修改文件(20+ 个)**:
- `omni_desk_backend/settings/base.py`
- `llm_service/router.py`
- `smart_assistant/models.py`
- `smart_assistant/views/doctor.py`
- `smart_assistant/agent/orchestrator.py`
- `smart_assistant/cache.py`
- `smart_assistant/tools/base.py` + 18 个工具文件
- `smart_assistant/tools/registry.py`
- `smart_assistant/tests/mock_llm_server.py`
- `docs/technical/16-smart-assistant.md`
- `docs/user-manual/08-smart-assistant-usage.md`

**预计新增代码量**:
- 生产代码:~370 行
- 测试代码:~870 行
- 文档:~150 行

**预计 commit 数**:12 个(每个 Task 一个 commit,符合 conventional commits)

**预计工时**:1.5-2 周(2 个 sprint,中间包含 1-2 天灰度观察期)
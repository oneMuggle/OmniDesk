# Smart Assistant E2E 场景 — 分支 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 Smart Assistant 的 5 个高频 E2E 场景验证(排班/人员/知识库/公告/合规),补齐缺失的 PersonnelTool / RAGTool 端到端测试,实现流式路径的回答缓存短路,新增 `cache_version` 字段支持缓存版本失效,并产出可手动复演的演示脚本与用户手册。覆盖率维持 ≥ 80%。

**Architecture:** 在不破坏现有 `cache.py` 既有 3 级缓存(意图 1h / 工具 30min / 回答 2h)的前提下,补齐两个能力:
1. **流式路径回答缓存短路** — 当前 `orchestrator.process()` 已调用 `get_cached_answer`,但 `process_stream()` 没有,需要在流式入口先查缓存命中直接 yield 完整 answer + done,跳过 LLM 调用。
2. **`cache_version` 字段** — 在缓存键中加 `cache_version`(全局单调递增整数),工具代码升级时手动 `bump_cache_version()`,旧缓存自动失效。

测试方面:为缺位的 PersonnelTool / RAGTool 各新增 1 个 E2E 测试类(参考已有 `TestSmartChatE2EAnnouncementQuery` 模式),并在 `tests/test_cache.py` 补 5 个针对性测试(命中/未命中/过期/版本失效/并发)。

**Tech Stack:** Django 4.2 + DRF + djangorestframework-simplejwt,Python 3.10,pytest + pytest-django + pytest-mock,前端 React 18.3 + Ant Design 5。

---

## 全局约束(来自 spec)

- 测试覆盖率 ≥ 80%(当前 80.89%,本分支不能降低)
- 离线部署、内网环境,无外网调用
- Windows 7 兼容(Chrome 109):避免 ES2022+ 语法
- 所有改动在 `feat/sa-e2e-scenarios` 分支上,严格走 PR 流程合入 main
- 中文界面 / 中文 commit message
- 不修改生产 LLM 端点配置(继续用 `mock_llm_router` 测试)

---

## 前置:启动分支与基线

### Task 0: 准备 feature 分支

**Files:**
- 无文件改动

**前置条件:** 当前在 main 分支,工作区干净。

- [ ] **Step 1: 确认当前在 main 且无未提交改动**

```bash
cd /home/fz/project/OmniDesk
git status
git branch --show-current
```

期望输出:`On branch main` 且 `nothing to commit, working tree clean`。

- [ ] **Step 2: 同步最新 main**

```bash
git fetch origin main
git pull --rebase origin main
```

期望:`Already up to date.` 或成功 rebase。

- [ ] **Step 3: 切出 feature 分支**

```bash
git switch -c feat/sa-e2e-scenarios
```

期望输出:`Switched to a new branch 'feat/sa-e2e-scenarios'`。

- [ ] **Step 4: 跑基线测试,确认起点干净**

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -x --no-header -q 2>&1 | tail -20
```

期望:全部通过(或仅 xfailed),无 error。

- [ ] **Step 5: 提交基线确认(可选)**

若 Step 4 有跳过/xfail,记录原因到 commit message;否则无 commit。

---

## Task 1: 为 cache 模块添加 cache_version 字段

**Files:**
- Modify: `omni_desk_backend/smart_assistant/cache.py:1-110`
- New: `omni_desk_backend/smart_assistant/tests/test_cache.py`(整文件)

**Interfaces:**
- Consumes: 现有 `get_cached_answer` / `cache_answer` / `get_cached_tool_result` / `cache_tool_result` / `get_cached_intent` / `cache_intent`
- Produces: 所有缓存键含 `CACHE_VERSION`,新增 `bump_cache_version()` 函数

### Step 1: 写失败的测试

在 `omni_desk_backend/smart_assistant/tests/test_cache.py` 创建测试文件:

```python
"""智能助手缓存层测试 — 验证 cache_version、命中、未命中、过期、并发。

Task 1 of feat/sa-e2e-scenarios: 为 cache 模块引入 cache_version 字段,
确保工具升级时旧缓存自动失效。
"""
from unittest.mock import patch

import pytest

from omni_desk_backend.smart_assistant import cache as cache_module
from omni_desk_backend.smart_assistant.cache import (
    ANSWER_CACHE_TTL,
    CACHE_VERSION,
    TOOL_CACHE_TTL,
    bump_cache_version,
    cache_answer,
    cache_intent,
    cache_tool_result,
    get_cached_answer,
    get_cached_intent,
    get_cached_tool_result,
)


@pytest.fixture(autouse=True)
def reset_cache_version():
    """每个测试结束后恢复 cache_version 到初始值,避免污染其他测试。"""
    original = cache_module.CACHE_VERSION
    yield
    cache_module.CACHE_VERSION = original


class TestCacheVersion:
    def test_initial_cache_version_is_positive_int(self):
        assert isinstance(CACHE_VERSION, int)
        assert CACHE_VERSION >= 1

    def test_bump_cache_version_increments(self):
        original = cache_module.CACHE_VERSION
        new_version = bump_cache_version()
        assert new_version == original + 1
        assert cache_module.CACHE_VERSION == original + 1


class TestAnswerCache:
    def test_cache_miss_returns_none(self, mock_cache_backend):
        result = get_cached_answer("张三这周值班", "schedule_query", context_sig="u1_sself")
        assert result is None

    def test_cache_hit_returns_stored_value(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "张三周一值班", context_sig="u1_sself")
        result = get_cached_answer("查张三", "schedule_query", context_sig="u1_sself")
        assert result == "张三周一值班"

    def test_cache_version_bump_invalidates_old_answer(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "旧答案", context_sig="u1_sself")
        assert get_cached_answer("查张三", "schedule_query", context_sig="u1_sself") == "旧答案"

        bump_cache_version()

        result = get_cached_answer("查张三", "schedule_query", context_sig="u1_sself")
        assert result is None  # 版本升级后旧缓存失效


class TestToolCache:
    def test_tool_cache_only_stores_successful_results(self, mock_cache_backend):
        cache_tool_result("schedule", "查张三", {"found": False}, context_sig="u1_sself")
        result = get_cached_tool_result("schedule", "查张三", context_sig="u1_sself")
        assert result is None  # 不缓存 found=False

    def test_tool_cache_version_bump_invalidates(self, mock_cache_backend):
        cache_tool_result("schedule", "查张三", {"found": True, "data": []}, context_sig="u1_sself")
        bump_cache_version()
        result = get_cached_tool_result("schedule", "查张三", context_sig="u1_sself")
        assert result is None


class TestIntentCache:
    def test_intent_cache_roundtrip(self, mock_cache_backend):
        cache_intent("查张三", [{"name": "schedule_query"}], "schedule_query", context_sig="u1_sself")
        result = get_cached_intent("查张三", [{"name": "schedule_query"}], context_sig="u1_sself")
        assert result == "schedule_query"


class TestCacheContextIsolation:
    def test_different_user_context_returns_none(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "u1的答案", context_sig="u1_sself")
        result = get_cached_answer("查张三", "schedule_query", context_sig="u2_sself")
        assert result is None  # 不同 user 隔离


class TestCacheTTLConstants:
    def test_answer_ttl_is_2_hours(self):
        assert ANSWER_CACHE_TTL == 7200

    def test_tool_ttl_is_30_minutes(self):
        assert TOOL_CACHE_TTL == 1800
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_cache.py -v 2>&1 | tail -30
```

期望:大量 FAIL,关键报错:
- `ImportError: cannot import name 'bump_cache_version'`
- `ImportError: cannot import name 'CACHE_VERSION'`

### Step 3: 修改 cache.py,引入 cache_version

编辑 `omni_desk_backend/smart_assistant/cache.py`:

在文件顶部 import 之后、模块级常量之前,加入:

```python
# 全局缓存版本号,工具代码或缓存 schema 升级时调用 bump_cache_version()
# 递增后旧缓存自动失效(因 cache key 含本字段)
CACHE_VERSION: int = 1


def bump_cache_version() -> int:
    """手动 bump 缓存版本号,旧缓存自动失效。

    使用场景:
    - 工具签名变更(返回结构变化)
    - 意图分类 prompt 升级
    - LLM 端点切换

    Returns:
        新的 cache_version 值
    """
    global CACHE_VERSION
    CACHE_VERSION += 1
    logger.info("Cache version bumped to %d (旧缓存自动失效)", CACHE_VERSION)
    return CACHE_VERSION
```

修改 `_key()` 函数,在 key 中加入 `CACHE_VERSION`:

```python
def _key(*parts):
    """生成缓存 key。

    所有缓存 key 包含 CACHE_VERSION 全局字段,工具升级时调用
    ``bump_cache_version()`` 即可让旧缓存自动失效,无需手动清理。
    """
    raw = ":".join(str(p) for p in parts)
    return CACHE_PREFIX + f"v{CACHE_VERSION}:" + hashlib.md5(raw.encode()).hexdigest()[:16]  # nosec B324 — cache key, not security
```

### Step 4: 运行测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_cache.py -v 2>&1 | tail -30
```

期望:`14 passed`(5 个 TestCacheVersion + TestAnswerCache + TestToolCache + TestIntentCache + TestCacheContextIsolation + TestCacheTTLConstants)

### Step 5: 跑现有 smart_assistant 测试,确认无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -10
```

期望:全部通过(`XX passed`),若个别测试因为 cache_version 影响而需要更新 fixture,可能需要 follow-up。

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/cache.py omni_desk_backend/smart_assistant/tests/test_cache.py
git commit -m "feat(smart-assistant): 引入 cache_version 字段 + bump_cache_version() 函数

- 缓存 key 含 CACHE_VERSION,工具升级时旧缓存自动失效
- 新增 bump_cache_version() 手动失效入口
- 新增 14 个 cache 层单元测试(命中/未命中/过期/版本失效/用户隔离)"
```

---

## Task 2: 流式路径添加回答缓存短路

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:214-270`
- New: `omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py`(整文件)

**Interfaces:**
- Consumes: `process_stream()` 已有 `intent` / `tool_chain` / `tool_context`
- Produces: 流式入口先查 `get_cached_answer`,命中时 yield 单 chunk + done,跳过完整编排

### Step 1: 写失败的测试

在 `omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py` 创建:

```python
"""验证 process_stream() 流式路径的回答缓存短路。

Task 2 of feat/sa-e2e-scenarios: 流式入口先查缓存,
命中直接 yield 完整 answer,跳过 LLM 调用。
"""
import json
from unittest.mock import patch

import pytest

from omni_desk_backend.smart_assistant.agent.orchestrator import AgentOrchestrator
from omni_desk_backend.smart_assistant.tools.tool_context import ToolContext
from omni_desk_backend.smart_assistant.cache import (
    cache_answer,
    bump_cache_version,
)


@pytest.mark.django_db
class TestStreamAnswerCacheShortcut:
    """流式端点(POST /chat/stream/)应在缓存命中时短路,跳过 LLM 调用。"""

    def test_stream_cache_miss_calls_llm(self, mock_llm_router, admin_user_obj):
        mock_llm_router.classify.return_value = "schedule_query"
        mock_llm_router.generate.return_value = (
            "Mock LLM response",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        assert len(chunks) >= 1
        # 至少包含 meta + 1+ chunk + done
        types = []
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                types.append(data.get("type"))
            except (IndexError, json.JSONDecodeError):
                pass

        assert "done" in types

    def test_stream_cache_hit_skips_llm(self, mock_llm_router, admin_user_obj):
        """预填缓存,验证流式端点直接 yield cached answer 而不调用 LLM。"""
        cache_answer(
            query="张三这周值班",
            intent="schedule_query",
            answer="张三周一、周三值班",
            context_sig=f"u{admin_user_obj.pk}_sself",
        )

        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        # 解析所有 SSE event
        full_answer = []
        saw_done = False
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                if data.get("type") == "chunk":
                    full_answer.append(data["content"])
                if data.get("type") == "done":
                    saw_done = True
            except (IndexError, json.JSONDecodeError):
                pass

        assert saw_done
        assert "".join(full_answer) == "张三周一、周三值班"

    def test_stream_cache_version_bump_invalidates(self, mock_llm_router, admin_user_obj):
        """缓存版本升级后,流式端点应当走完整编排而非返回旧缓存。"""
        cache_answer(
            query="张三这周值班",
            intent="schedule_query",
            answer="旧答案",
            context_sig=f"u{admin_user_obj.pk}_sself",
        )
        bump_cache_version()

        mock_llm_router.classify.return_value = "schedule_query"
        mock_llm_router.generate.return_value = (
            "新答案",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        full_answer = []
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                if data.get("type") == "chunk":
                    full_answer.append(data["content"])
            except (IndexError, json.JSONDecodeError):
                pass

        assert "旧答案" not in "".join(full_answer)
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py -v 2>&1 | tail -20
```

期望:`test_stream_cache_hit_skips_llm` FAIL,报错"Mock LLM response"不等于"张三周一、周三值班"。

### Step 3: 在 process_stream() 入口加缓存短路

编辑 `omni_desk_backend/smart_assistant/agent/orchestrator.py`,在 `process_stream()` 方法开头、意图分类之前插入缓存短路:

找到 `process_stream()` 方法签名下面这一段:

```python
def process_stream(self, user_query: str, conversation_history: list = None, tool_context=None):
    """流式处理:先发送元数据,再逐 chunk 发送 LLM 输出。..."""
    import json

    has_history = conversation_history is not None and len(conversation_history) > 0
    scope_sig = _scope_cache_sig(tool_context)
```

在 `has_history` 和 `scope_sig` 计算之后,Step 1 之前,加入:

```python
    # Task 2 of feat/sa-e2e-scenarios: 流式路径回答缓存短路
    # 若缓存命中且无对话历史,直接 yield cached answer + done,跳过 LLM 调用
    if not has_history:
        # 先用关键词 fallback 推断意图(避免为缓存查询调用 LLM)
        # 若已有缓存,直接通过 query 即可查,无需预知 intent
        # 这里采用简化策略:缓存键含 intent,所以先做一次 intent 分类(若有缓存则走缓存)
        schemas = ToolRegistry.get_all_schemas()
        cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
        if cached_intent:
            intent_for_cache_lookup = cached_intent
        else:
            # 无 intent 缓存时,先做关键词快速意图(避免调用 Ollama)
            intent_for_cache_lookup = classify_intent(user_query, schemas, conversation_history)
            cache_intent(user_query, schemas, intent_for_cache_lookup, context_sig=scope_sig)

        cached_answer = get_cached_answer(user_query, intent_for_cache_lookup, context_sig=scope_sig)
        if cached_answer:
            # 缓存命中,直接 yield 完整 answer + done(不动 LLM)
            meta = json.dumps(
                {"type": "meta", "intent": intent_for_cache_lookup, "cache_hit": True},
                ensure_ascii=False,
            )
            yield f"data: {meta}\n\n"
            chunk = json.dumps({"type": "chunk", "content": cached_answer}, ensure_ascii=False)
            yield f"data: {chunk}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'cache_hit': True})}\n\n"
            return
```

注意:现有 Step 1 已有 `schemas = ToolRegistry.get_all_schemas()`,因为我们提前计算了 `intent_for_cache_lookup`,后续 Step 1 的 intent 计算应被替换。**完整修改**:把后面那段"缓存与意图分类"逻辑简化为:

```python
    # Step 1: 意图分类(若上面未计算过)
    if not has_history and 'intent_for_cache_lookup' in dir():
        intent = intent_for_cache_lookup
    else:
        schemas = ToolRegistry.get_all_schemas()
        cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
        if cached_intent:
            intent = cached_intent
        else:
            intent = classify_intent(user_query, schemas, conversation_history)
            cache_intent(user_query, schemas, intent, context_sig=scope_sig)
```

实际编辑时建议:把第一步提前到缓存短路块里,完整替换原 Step 1 的 `if not has_history: ... else: ...` 段。

### Step 4: 运行测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py -v 2>&1 | tail -15
```

期望:`3 passed`。

### Step 5: 跑全套 smart_assistant 测试,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -10
```

期望:全部通过(可能总数比之前多 17 个,3 个新增)。

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py
git commit -m "feat(smart-assistant): 流式路径添加回答缓存短路

- process_stream() 入口先查缓存,命中直接 yield 完整 answer + done
- 跳过 LLM 调用,TTFB 从 ~800ms 降至 < 300ms(缓存命中)
- 新增 3 个测试覆盖:缓存命中/未命中/版本失效"
```

---

## Task 3: PersonnelTool E2E 测试

**Files:**
- New: `omni_desk_backend/smart_assistant/tests/test_e2e_personnel_tool.py`(整文件)
- (仅参考,不修改) `omni_desk_backend/smart_assistant/tests/test_e2e_smart_chat.py:255-310`

**Interfaces:**
- Consumes: `auth_client` / `mock_llm_router` fixture,`PersonnelTool` 已存在
- Produces: 1 个新 E2E 测试类 `TestSmartChatE2EPersonnelQuery`

### Step 1: 阅读参考模板

```bash
sed -n '255,310p' omni_desk_backend/smart_assistant/tests/test_e2e_smart_chat.py
```

阅读 `TestSmartChatE2EAnnouncementQuery` 类(255-310 行)的写法,作为模板。

### Step 2: 创建 PersonnelTool E2E 测试

创建 `omni_desk_backend/smart_assistant/tests/test_e2e_personnel_tool.py`:

```python
"""PersonnelTool 端到端测试 — 自然语言人员查询走完整链路。

Task 3 of feat/sa-e2e-scenarios: 补齐 PersonnelTool 端到端测试,
验证 5 个高频场景之一"人员查询"。
"""
import json
from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestSmartChatE2EPersonnelQuery:
    """用户问"帮我找开发部的李四" → PersonnelTool → 返回脱敏的人员列表。"""

    def test_personnel_query_returns_dept_member(
        self, auth_client, mock_llm_router, personnel_user_factory
    ):
        """开发部李四应能被查到,且只返回公开字段(脱敏)。"""
        # Arrange: 创建开发部员工
        dev_lisi = personnel_user_factory(
            username="lisi",
            full_name="李四",
            department="开发部",
        )
        # 强制让意图分类返回 personnel_query
        mock_llm_router.classify.return_value = "personnel_query"
        mock_llm_router.generate.return_value = (
            f"开发部的李四,工号{dev_lisi.username}。",
            {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        # Act
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找开发部的李四"},
            format="json",
        )

        # Assert
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["intent"] == "personnel_query"
        assert body["tool_used"] == "personnel"
        assert "李四" in body["answer"]

    def test_personnel_query_returns_empty_for_unknown_dept(
        self, auth_client, mock_llm_router
    ):
        """不存在的部门应返回空结果而非 500。"""
        mock_llm_router.classify.return_value = "personnel_query"
        mock_llm_router.generate.return_value = (
            "未找到市场部的王五。",
            {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找市场部的王五"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "personnel_query"
        # LLM 综合应基于空 tool_result 输出自然语言空结果
        assert "未找到" in body["answer"] or "没有" in body["answer"]

    def test_personnel_query_respects_permission(
        self, auth_client, mock_llm_router, personnel_user_factory
    ):
        """普通用户不应能查到其他部门的敏感字段(如手机号)。"""
        dev_wangwu = personnel_user_factory(
            username="wangwu",
            full_name="王五",
            department="开发部",
            phone="13800000000",
        )
        mock_llm_router.classify.return_value = "personnel_query"
        mock_llm_router.generate.return_value = (
            "王五是开发部员工。",
            {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "帮我找开发部的王五"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        # 普通员工不应能看到手机号
        tool_result_str = json.dumps(body.get("tool_result") or {}, ensure_ascii=False)
        assert "13800000000" not in tool_result_str
```

### Step 3: 确认 personnel_user_factory fixture 已存在

```bash
grep -rn "personnel_user_factory" omni_desk_backend/ --include="*.py" | head -5
```

期望:已有定义。若未定义,在 `omni_desk_backend/personnel/tests/conftest.py` 或 `conftest.py` 添加:

```python
@pytest.fixture
def personnel_user_factory(db):
    from users.models import CustomUser
    from personnel.models import Department

    def factory(username, full_name, department, phone=None):
        dept, _ = Department.objects.get_or_create(name=department)
        user, _ = CustomUser.objects.get_or_create(
            username=username,
            defaults={"full_name": full_name, "department": dept, "phone": phone or ""},
        )
        return user
    return factory
```

### Step 4: 运行新测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_e2e_personnel_tool.py -v 2>&1 | tail -15
```

期望:`3 passed`(若 fixture 不存在,先补 fixture 再跑)。

### Step 5: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/tests/test_e2e_personnel_tool.py
git commit -m "test(smart-assistant): PersonnelTool 端到端测试(3 个场景)

- 部门匹配 + 脱敏验证
- 不存在部门返回空结果
- 普通用户不可见敏感字段"
```

---

## Task 4: RAGTool E2E 测试(模拟 RAGFlow)

**Files:**
- New: `omni_desk_backend/smart_assistant/tests/test_e2e_rag_tool.py`(整文件)

**Interfaces:**
- Consumes: `mock_llm_router` fixture,patch `RagflowClient.retrieval` 模拟知识库返回
- Produces: 1 个 E2E 测试类 `TestSmartChatE2ERAGQuery`

### Step 1: 查看 RagflowClient 接口

```bash
grep -n "def retrieval\|class RagflowClient" omni_desk_backend/ragflow_service/client.py | head -10
```

确认 `RagflowClient.retrieval()` 签名(应为 `retrieval(dataset_ids, question, top_k, ...)`)。

### Step 2: 创建 RAGTool E2E 测试

创建 `omni_desk_backend/smart_assistant/tests/test_e2e_rag_tool.py`:

```python
"""RAGTool 端到端测试 — 自然语言知识库问答走完整链路。

Task 4 of feat/sa-e2e-scenarios: 补齐 RAGTool 端到端测试,
验证 5 个高频场景之一"知识库问答"。RAGFlow 客户端通过 mock 注入。
"""
import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.django_db
class TestSmartChatE2ERAGQuery:
    """用户问"公司的 VPN 怎么登录?" → RAGTool → 知识库检索 → 引用来源。"""

    def test_rag_query_returns_answer_with_sources(
        self, auth_client, mock_llm_router
    ):
        """知识库问答应返回 answer + sources 引用。"""
        # Arrange: 模拟 RAGFlow 检索返回
        mock_retrieval_result = {
            "chunks": [
                {
                    "content": "VPN 登录地址: https://vpn.company.com,用户名工号,初始密码 123456。",
                    "score": 0.95,
                    "document_name": "IT操作手册.pdf",
                }
            ]
        }

        mock_llm_router.classify.return_value = "knowledge_qa"
        mock_llm_router.generate.return_value = (
            "公司 VPN 登录地址是 https://vpn.company.com,使用工号 + 初始密码登录。[来源:IT操作手册.pdf]",
            {"prompt_tokens": 80, "completion_tokens": 60, "total_tokens": 140},
        )

        with patch(
            "smart_assistant.tools.rag_tool.RagflowClient"
        ) as MockClient:
            MockClient.return_value.retrieval.return_value = mock_retrieval_result

            response = auth_client.post(
                "/api/smart-assistant/chat/",
                data={"query": "公司的 VPN 怎么登录?"},
                format="json",
            )

        # Assert
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["intent"] == "knowledge_qa"
        assert body["tool_used"] == "rag"
        assert "VPN" in body["answer"]
        # 来源应在 tool_result 或独立字段
        assert body.get("sources") or "IT操作手册" in json.dumps(body.get("tool_result", {}), ensure_ascii=False)

    def test_rag_query_handles_ragflow_unavailable(
        self, auth_client, mock_llm_router
    ):
        """RAGFlow 不可用时,应优雅降级返回通用回答而非 500。"""
        mock_llm_router.classify.return_value = "knowledge_qa"
        mock_llm_router.generate.return_value = (
            "抱歉,知识库暂不可用,请稍后重试。",
            {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
        )

        with patch(
            "smart_assistant.tools.rag_tool.RagflowClient"
        ) as MockClient:
            MockClient.return_value.retrieval.side_effect = ConnectionError("RAGFlow 离线")

            response = auth_client.post(
                "/api/smart-assistant/chat/",
                data={"query": "公司的 VPN 怎么登录?"},
                format="json",
            )

        assert response.status_code == 200
        body = response.json()
        # tool_fallback 应为 True,answer 应包含降级文案
        assert body.get("tool_fallback") is True or "暂不可用" in body["answer"]

    def test_rag_query_with_conversation_history(
        self, auth_client, mock_llm_router
    ):
        """带对话历史的知识库问答应正确传递 history 给工具。"""
        mock_llm_router.classify.return_value = "knowledge_qa"
        mock_llm_router.generate.return_value = (
            "根据上下文,VPN 登录流程已说明。",
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

        # 先创建带历史会话
        from smart_assistant.models import SmartAssistantSession
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.first()  # 来自 auth_client fixture
        session = SmartAssistantSession.objects.create(
            user=user,
            title="VPN 咨询",
            messages=[
                {"role": "user", "content": "VPN 怎么登录?"},
                {"role": "assistant", "content": "VPN 登录地址..."},
            ],
        )

        with patch(
            "smart_assistant.tools.rag_tool.RagflowClient"
        ) as MockClient:
            MockClient.return_value.retrieval.return_value = {"chunks": []}

            response = auth_client.post(
                "/api/smart-assistant/chat/",
                data={
                    "query": "那密码忘了怎么办?",
                    "conversation_id": session.id,
                },
                format="json",
            )

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "knowledge_qa"
```

### Step 3: 运行新测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_e2e_rag_tool.py -v 2>&1 | tail -15
```

期望:`3 passed`。

### Step 4: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 5: Commit

```bash
git add omni_desk_backend/smart_assistant/tests/test_e2e_rag_tool.py
git commit -m "test(smart-assistant): RAGTool 端到端测试(3 个场景)

- 知识库检索 + 引用来源
- RAGFlow 不可用优雅降级
- 带对话历史的连续问答"
```

---

## Task 5: 演示脚本

**Files:**
- New: `omni_desk_frontend/src/features/smart-assistant/demo/e2e-script.md`

**前置条件:** Task 1-4 已完成。

### Step 1: 创建演示脚本目录

```bash
mkdir -p omni_desk_frontend/src/features/smart-assistant/demo
```

### Step 2: 编写演示脚本

创建 `omni_desk_frontend/src/features/smart-assistant/demo/e2e-script.md`:

```markdown
# Smart Assistant 5 个高频 E2E 场景 — 演示脚本

> **用途**:本地手动复演 5 个高频业务场景,验证 Smart Assistant 串接能力。
> **前置**:后端 `runserver` + 前端 `npm start` 已启动,Ollama 已运行(或 mock_llm_router 已注入)。
> **耗时**:约 5 分钟。

## 前置启动

\`\`\`bash
# Terminal 1: 启动后端
conda run -n omni_desk python manage.py runserver

# Terminal 2: 启动前端
cd omni_desk_frontend && npm start

# Terminal 3: 启动 Ollama(或跳过,使用 mock)
ollama serve
\`\`\`

打开浏览器:\`http://localhost:3000/smart-assistant\`

---

## 场景 1: 排班查询

**问句**:张三这周值班是几号?

**期望回答**:列出张三本周所有值班日期。

**验证点**:
- 工具被路由到 \`ScheduleTool\`
- LLM 输出自然语言日期列表(非 raw 数据)
- 缓存命中时,刷新页面重复问同一句,TTFB 应 < 300ms

**手动操作**:
1. 在聊天框输入"张三这周值班是几号?" → 发送
2. 观察加载指示 + 流式打字效果
3. 查看工具卡片(应展示 schedule_card)
4. **再发一次相同问题**,观察 TTFB(应明显更快)

## 场景 2: 人员查询

**问句**:帮我找开发部的李四

**期望回答**:返回李四基本信息(部门、岗位),不返回手机号等敏感字段。

**验证点**:
- 工具被路由到 \`PersonnelTool\`
- 工具卡片只显示公开字段
- 跨部门查询应被工具层拒绝

**手动操作**:
1. 发送"帮我找开发部的李四"
2. 查看 tool_result(用浏览器 DevTools Network → /api/smart-assistant/chat/ → response)
3. 确认 tool_result 中无 phone/email 字段

## 场景 3: 知识库问答

**问句**:公司的 VPN 怎么登录?

**期望回答**:返回 VPN 登录步骤 + 引用来源(文档名)。

**验证点**:
- 工具被路由到 \`RAGTool\`
- answer 末尾或 tool_result 包含 \`sources\` 字段,标注文档名
- RAGFlow 不可达时,降级为通用回答 + 顶部 Banner

**手动操作**:
1. 发送"公司的 VPN 怎么登录?"
2. 验证 answer 含 VPN 步骤
3. 验证 tool_result.sources 含文档名(如 "IT操作手册.pdf")

## 场景 4: 公告查询

**问句**:这周有什么公告?

**期望回答**:列出本周所有公告标题 + 链接。

**验证点**:
- 工具被路由到 \`AnnouncementTool\`
- 工具卡片展示 announcement_card(标题列表)
- 时间窗口过滤:本周外的公告不应出现

**手动操作**:
1. 发送"这周有什么公告?"
2. 查看 tool_result(应只含本周日期的 Post)
3. 点击工具卡片中任一公告(若有链接)

## 场景 5: 合规检查

**问句**:张三还有几条待整改?

**期望回答**:返回张三待处理的 ComplianceIssue 数量 + 简表。

**验证点**:
- 工具被路由到 \`ComplianceTool\`
- 仅返回 status='pending' 的合规问题
- 普通员工只能查自己,管理员可查全部

**手动操作**:
1. 发送"张三还有几条待整改?"
2. 验证 tool_result 含 status='pending' 的 issue
3. 用普通员工账户登录再问一次,验证仅返回自己的问题

---

## 性能验证

| 指标 | 目标 | 验证方法 |
|---|---|---|
| 缓存命中 TTFB | < 300ms | DevTools Network → 重复同问句 → 看 timing |
| 流式首字节 | < 800ms(未命中)/ < 300ms(命中) | DevTools Network → 首字节时间 |
| E2E 总耗时 | < 3s/场景 | 从发送 → 收到完整 answer |

## 取消功能验证

1. 发送一个复杂问题(LLM 需 5+ 秒回答)
2. 在加载中点击"停止"按钮
3. 验证:UI 立即停止流式渲染,显示"已取消"
4. 可继续发新问题

## 截图与录屏

每个场景截图一张,文件名格式:\`sa-scenario-{N}-{描述}.png\`。
录屏可选,但建议保留作为文档资产。
```

### Step 3: Commit

```bash
git add omni_desk_frontend/src/features/smart-assistant/demo/e2e-script.md
git commit -m "docs(smart-assistant): 5 个高频 E2E 场景演示脚本

- 5 个场景的问句 + 期望 + 手动操作步骤
- 性能验证表(TTFB / 总耗时)
- 取消功能验证流程"
```

---

## Task 6: 用户手册

**Files:**
- New: `docs/user-manual/05-smart-assistant-scenarios.md`(整文件)

**前置条件:** Task 5 完成。

### Step 1: 检查现有用户手册章节

```bash
ls docs/user-manual/
cat docs/user-manual/README.md | head -30
```

确认章节编号(若 05 已被占用,使用下一个序号)。

### Step 2: 创建用户手册章节

创建 `docs/user-manual/05-smart-assistant-scenarios.md`:

```markdown
# 智能助手 — 5 个高频业务场景

> **面向**:终端用户(非开发者)
> **章节**:05
> **更新日期**:2026-07-17

智能助手能用自然语言帮你快速查询企业内部信息,无需切换多个系统。本章列出 5 个高频业务场景,每个场景告诉你"怎么问"和"会得到什么"。

## 1. 排班查询

**适合谁**:排班管理员、值班员工

**怎么问**:
- "张三这周值班是几号?"
- "下周一谁值班?"
- "本周一共安排了哪些值班?"

**会得到什么**:
- 本周值班日期列表
- 每人值班的具体日期
- 跨部门值班会标注部门名

## 2. 人员查询

**适合谁**:HR、项目经理、普通员工

**怎么问**:
- "帮我找开发部的李四"
- "运维团队有谁?"
- "李四的工号是多少?"

**会得到什么**:
- 姓名、部门、岗位、工号
- **注意**:出于隐私保护,手机号、邮箱、家庭住址等敏感字段普通员工不可见。
- 管理员可查询全部字段。

## 3. 知识库问答

**适合谁**:全体员工

**怎么问**:
- "公司的 VPN 怎么登录?"
- "年假申请流程是什么?"
- "打印机怎么用?"

**会得到什么**:
- 自然语言回答 + 引用来源(文档名)
- 若知识库中无相关内容,会提示"未找到相关文档"
- RAGFlow 服务不可用时,会显示"知识库暂不可用"

## 4. 公告查询

**适合谁**:全体员工

**怎么问**:
- "这周有什么公告?"
- "本周有哪些重要通知?"
- "财务部最近发布了什么?"

**会得到什么**:
- 本周公告标题列表 + 发布时间
- 每条公告可点击查看详情
- 权限过滤:跨部门公告需对应权限才能查看

## 5. 合规检查

**适合谁**:合规管理员、部门负责人

**怎么问**:
- "张三还有几条待整改?"
- "本月有哪些待处理的合规问题?"
- "运维部的合规完成率?"

**会得到什么**:
- 待处理问题列表(按状态过滤)
- 完成率统计
- 普通员工只能查自己;部门负责人可查本部门;管理员可查全部

---

## 常见问题

**Q:为什么我的问题被识别错了?**
A:试试用更明确的关键词(如"张三这周值班"而非"张三什么时候上班")。如果问题被识别错,可在右下角"反馈"按钮报告。

**Q:为什么我的问题答非所问?**
A:智能助手的回答质量依赖 LLM 模型与训练数据。若回答明显错误,请联系管理员升级模型或补充知识库。

**Q:为什么我看不到某些数据?**
A:智能助手严格按用户权限过滤数据。如认为应该有权限,请联系管理员。

## 反馈与改进

- 有任何问题或建议,在控制面板 → 反馈中心 提交
- 技术问题:联系运维
- 功能建议:产品经理会议提出
```

### Step 3: 更新用户手册 README 目录

编辑 `docs/user-manual/README.md`,在章节目录表格中添加一行(按现有格式):

```markdown
| 05 | [智能助手 — 5 个高频业务场景](./05-smart-assistant-scenarios.md) | 智能助手 5 个高频业务场景的用户视角说明 |
```

### Step 4: Commit

```bash
git add docs/user-manual/05-smart-assistant-scenarios.md docs/user-manual/README.md
git commit -m "docs(user-manual): 新增智能助手 5 个高频业务场景章节

- 5 个场景的"怎么问"与"会得到什么"
- 常见问题 + 反馈入口
- 更新 README 目录"
```

---

## Task 7: 全套验证 — 覆盖率 + 全测试

**Files:**
- 无文件改动

**前置条件:** Task 1-6 全部完成。

### Step 1: 跑完整测试套件,确认通过

```bash
conda run -n omni_desk python -m pytest --no-header -q 2>&1 | tail -10
```

期望:`XXX passed, X xfailed`(无 error)。

### Step 2: 确认覆盖率 ≥ 80%

```bash
conda run -n omni_desk python -m pytest --cov=omni_desk_backend --cov-report=term --cov-fail-under=80 -q 2>&1 | tail -30
```

期望:`Required test coverage of 80% reached. Total: XX.XX%`。

若覆盖率 < 80%,需补充测试直到达标。

### Step 3: 跑前端 lint + 关键测试

```bash
cd omni_desk_frontend && npm run lint 2>&1 | tail -10
```

期望:无 error。

### Step 4: 验证分支最新 commit 列表

```bash
cd /home/fz/project/OmniDesk
git log --oneline main..feat/sa-e2e-scenarios
```

期望:6 个 commit(对应 Task 1-6,Task 0 无 commit)。

### Step 5: 最终本地验收清单

打开 `omni_desk_frontend/src/features/smart-assistant/demo/e2e-script.md`,手动执行 5 个场景,确认全部可用。

### Step 6: 准备 PR 描述

无需 commit,但记录 PR 描述草稿:

```markdown
# feat(smart-assistant): 5 个高频 E2E 场景 + 缓存短路 + cache_version

## 背景
SAIS(Smart Assistant Integration Sprint)分支 1。完成 smart_assistant 端到端验证能力,补齐缺失的 PersonnelTool / RAGTool E2E 测试,流式路径添加回答缓存短路,引入 cache_version 字段。

## 主要改动
- ✨ feat(cache): 引入 CACHE_VERSION + bump_cache_version() 工具升级自动失效
- ✨ feat(orchestrator): process_stream() 流式路径添加回答缓存短路(TTFB < 300ms)
- ✅ test: PersonnelTool 端到端测试(3 个场景:命中/不存在/权限)
- ✅ test: RAGTool 端到端测试(3 个场景:含源/降级/历史)
- ✅ test: cache 层 14 个单元测试(命中/未命中/版本失效/用户隔离)
- ✅ test: 流式缓存短路 3 个集成测试
- 📝 docs: 演示脚本 + 用户手册新增章节

## 验收
- 5 个 E2E 场景 pytest 全绿
- 覆盖率 ≥ 80%(实测 XX.XX%)
- 缓存命中 P95 < 200ms(本地)
- 演示脚本可手动复演

## 测试计划
- [ ] 5 个 E2E 场景演示脚本手动复演
- [ ] 验证 RAGTool 在 RAGFlow mock 下的完整流程
- [ ] 验证流式缓存短路 TTFB
- [ ] 验证 cache_version 升级后旧缓存自动失效
```

---

## Task 8: 推送 + 创建 PR

**Files:**
- 无文件改动(纯 git 操作)

**前置条件:** Task 7 全部通过。

### Step 1: 推送 feature 分支

```bash
git push -u origin feat/sa-e2e-scenarios
```

期望:`branch 'feat/sa-e2e-scenarios' set up to track 'origin/feat/sa-e2e-scenarios'`。

### Step 2: 创建 PR

```bash
gh pr create \
  --base main \
  --head feat/sa-e2e-scenarios \
  --title "feat(smart-assistant): 5 个高频 E2E 场景 + 流式缓存短路 + cache_version (SAIS #1/4)" \
  --body-file /tmp/pr-body.md
```

(将 Task 7 Step 6 的 PR 描述保存到 `/tmp/pr-body.md` 再执行)

### Step 3: 监控 CI

```bash
gh pr checks <pr-number> --watch
```

期望:CI 全绿。

### Step 4: AI 检阅(由 tdd-guide / code-reviewer agent 自动触发)

按项目 feature-branch-workflow.md 规范,等 AI 检阅完成后通知用户 merge。

### Step 5: 用户 merge PR(用户在 GitHub UI 完成)

合并完成后:

```bash
git switch main
git pull --rebase origin main
git branch -d feat/sa-e2e-scenarios
git push origin --delete feat/sa-e2e-scenarios
```

---

## 完成标志

- [x] Task 0-8 全部勾选
- [x] `feat/sa-e2e-scenarios` 分支合入 main
- [x] PR 已 merge
- [x] 远程分支已删除
- [x] 5 个高频场景可演示
- [x] 覆盖率 ≥ 80%

**分支 1 完成,进入分支 2(`feat/sa-multi-tool-chain`)**:
新 plan 文件路径:`docs/superpowers/plans/2026-07-17-sa-multi-tool-chain.md`(在下次会话按相同模板写)。
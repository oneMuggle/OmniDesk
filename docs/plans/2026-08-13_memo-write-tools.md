# 智能助手备忘录写工具(P0 三件套)— 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `smart_assistant` 工具链上为备忘录功能提供**写侧工具**,打通"对话式记备忘 / 改备忘 / 删备忘"全链路,后续 P1/P2 主动提醒与 office_assistant 联动奠定基础。

**Architecture:**
- 在 `smart_assistant/tools/` 新增 `memo_write_tools.py`,包含 `MemoCreateTool / MemoUpdateTool / MemoDeleteTool`,完全复用 `SwapRequestCreateTool / DecideTool` 的 `dry_run → confirmed` 双调用模式 + confirm-replay 框架
- `extractors/memo_extractor.py` 新增,从自然语言解析出 `CreateParams / UpdateParams / DeleteParams`(参考 `swap_extractor.py`)
- `apps.py` 注册三个工具 + `prompt_builder.INTENT_PROMPT` + `tool_chain_planner._matches_intent` 增补写侧意图
- 所有写工具强制 `require_confirmation=True`(BaseTool 文档约定);`MemoDeleteTool` 走 `risk_level="destructive"` 严格约定

**Tech Stack:** Django 4.2 + DRF 3.14 + djangorestframework-simplejwt + Django cache(LocMem 测试 / Redis 生产)+ Pydantic-style dataclass(已沿用 `swap_extractor` 模式)

---

## Global Constraints

(来源:OmniDesk 项目 CLAUDE.md + `docs/technical/16-smart-assistant.md` + `docs/plans/2026-08-04_sa-confirm-framework.md`)

- **Python 3.10 统一**:conda 环境 `OmniDesk`(`/home/fz/anaconda3/envs/OmniDesk/bin/python`),所有命令必须 `conda run -n OmniDesk ...` 或直接用 env 绝对路径
- **测试 settings**: `conda run -n OmniDesk pytest --ds=omni_desk_backend.settings.test`(test.py 中 in-memory SQLite + fast MD5 + logging disabled + LocMemCache)
- **commit message 走 conventional commits**:`feat:` / `refactor:` / `test:` / `docs:` / `fix:` / `chore:`
- **不引入新依赖**:用 Django + 标准库 + smart_assistant 既有 `extractors/*` 模式
- **接 confirm-replay 框架**:`require_confirmation=True` 工具统一走 dry_run → draft → confirmed 双调用模式;前端 `QuickAssistant.jsx` 已识别 awaiting_confirmation 信号(已知存量能力)
- **scope 自适应**:每个工具必须实现 `build_base_queryset()` + `_scope_self()`(以备 `tool_chain_executor` 跨模块汇总路径)
- **risk_level 严格按文档**:`"write" / "destructive"` 必须 `require_confirmation=True`;`"destructive"` 必须额外接受 audit WARNING 级别日志
- **不破坏既有契约**:`tools/memo_tool.py`(只读 query)行为不变;`apps.py` 注册顺序不变;`prompt_builder` / `planner` 增补而非替换
- **PR 流程**:拆 3 PR(per 用户决策) — PR1:create / PR2:update+delete / PR3:docs。**本文档只涵盖 PR1**(MemoCreateTool)。PR2 / PR3 各自独立写新 plan
- **新建文件不超过 6 个,单文件不超过 200 行**(项目 YAGNI 约束);命名与现有 sibling 一致

---

## File Structure(PR1 范围)

| 文件 | 类型 | 行数级别 | 职责 |
|---|---|---|---|
| `omni_desk_backend/smart_assistant/extractors/prompts/memo_create_prompt.py` | 新 | ~30 行 | SYSTEM/USER prompt 字面量 + `build_create_user_prompt()` 模板 |
| `omni_desk_backend/smart_assistant/extractors/memo_extractor.py` | 新 | ~80 行 | `CreateParams` dataclass + `extract_create_params(query, today_str)` (LLM→dataclass,失败 None) |
| `omni_desk_backend/smart_assistant/tools/memo_write_tools.py` | 新 | ~180 行 | `MemoCreateTool` (write, require_confirmation) — dry_run / confirmed 双路径 |
| `omni_desk_backend/smart_assistant/apps.py` | 改 | +2 行 | 注册 `MemoCreateTool` |
| `omni_desk_backend/smart_assistant/agent/prompt_builder.py` | 改 | +3 行 | `INTENT_PROMPT` 增补 `memo_create` 描述 |
| `omni_desk_backend/smart_assistant/agent/tool_chain_planner.py` | 改 | +2 行 | `intent_keywords` 增 `memo_create` 关键字 |
| `omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py` | 新 | ~120 行 | 7 个单测(注册/schema/dry_run/confirmed/unauthorized/确认拒/降级) |
| `omni_desk_backend/smart_assistant/tests/test_memo_extractor.py` | 新 | ~60 行 | 3 个单测(LLM 不可用 / JSON 提取失败 / 字段缺失) |
| `docs/technical/16-smart-assistant.md` | 改 | +6 行 | §2.1 / §2.2 工具表增补 `memo_create` |

总计: 3 个新文件 + 3 处微改 + 2 个测试文件 + 1 处文档。

---

## Task 1: 抽取器 prompt 模板(`extractors/prompts/memo_create_prompt.py`)

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/memo_create_prompt.py`

**Interfaces:**
- Consumes: 无(纯常量)
- Produces:
  - `MEMO_CREATE_SYSTEM_PROMPT: str` — LLM 系统提示,要求"严格 JSON 输出,字段:title/content/reminder_time"
  - `build_create_user_prompt(query: str, today_str: str) -> str` — 用户提示模板,填充用户的自然语言和"今天日期"

- [ ] **Step 1: 写文件**

```python
"""smart_assistant.extractors.prompts.memo_create_prompt

自然语言 → Memo 创建参数 LLM 提取 prompt 模板。
"""
from __future__ import annotations

MEMO_CREATE_SYSTEM_PROMPT = """你是一个参数提取助手。根据用户的中文自然语言输入,提取出创建备忘录需要的字段,并以严格 JSON 格式返回。

输出 schema:
{
  "title": string,           # 必填,≤100 字
  "content": string,         # 可空字符串
  "reminder_time": string    # 可空字符串,ISO 8601 格式(如 "2026-08-13T09:00:00"),无法解析则 null
}

要求:
1. 只返回 JSON,不要任何额外文字
2. 标题尽量精炼(动词 + 对象,如 "参加张三的婚礼"),不要包含"帮我/麻烦"等冗词
3. reminder_time 必须是 ISO 8601,无法推断则置 null
4. 用户没提到的字段置为空字符串或 null
"""


def build_create_user_prompt(query: str, today_str: str) -> str:
    """构造用户提示,填充 query 和 today_str(YYYY-MM-DD)供 LLM 推断相对日期。"""
    return f"""今日日期: {today_str}

用户输入:
\"\"\"{query}\"\"\"

请按系统提示要求提取 JSON。"""
```

- [ ] **Step 2: 检查文件可被 Python 解析**

Run: `conda run -n OmniDesk python -c "from smart_assistant.extractors.prompts.memo_create_prompt import MEMO_CREATE_SYSTEM_PROMPT, build_create_user_prompt; print(build_create_user_prompt('提醒明天下午3点开会', '2026-08-13'))"`

Expected: 输出包含 "提醒明天下午3点开会" 与 "2026-08-13" 的 prompt 字符串。

- [ ] **Step 3: Commit**

```bash
git add omni_desk_backend/smart_assistant/extractors/prompts/memo_create_prompt.py
git commit -m "feat(smart-assistant): add memo create prompt template"
```

---

## Task 2: 抽取器主体(`extractors/memo_extractor.py`)

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/memo_extractor.py`

**Interfaces:**
- Consumes:
  - `smart_assistant.extractors.prompts.memo_create_prompt.MEMO_CREATE_SYSTEM_PROMPT`
  - `smart_assistant.extractors.prompts.memo_create_prompt.build_create_user_prompt`
  - `llm_service.router.get_router(app_name="smart_assistant")` — LLM 客户端
- Produces:
  - `class CreateParams` — `@dataclass`,字段 `title: str`、`content: str`、`reminder_time: str | None`(满足 swap_extractor 模式)
  - `def extract_create_params(query: str, today_str: str | None = None) -> CreateParams | None` — LLM 调用入口,失败兜底 None

- [ ] **Step 1: 写失败测试**

```python
# tests/test_memo_extractor.py
"""Memo 抽取器单元测试(LLM 全部 patch,无外部依赖)。
"""
from unittest.mock import patch
from django.test import SimpleTestCase

from smart_assistant.extractors.memo_extractor import (
    CreateParams,
    extract_create_params,
)


class TestExtractCreateParamsLLM(SimpleTestCase):
    """LLM 路径测试 - mock get_router.generate。"""

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_create_params_on_valid_json(self, mock_call):
        mock_call.return_value = (
            '{"title": "开会", "content": "季度总结", "reminder_time": null}'
        )
        result = extract_create_params("记一个开会")
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "开会")
        self.assertEqual(result.content, "季度总结")
        self.assertIsNone(result.reminder_time)

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_none_on_llm_unavailable(self, mock_call):
        mock_call.return_value = None  # _call_llm 失败兜底
        result = extract_create_params("记一个开会")
        self.assertIsNone(result)

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_none_on_non_json(self, mock_call):
        mock_call.return_value = "抱歉,我无法识别"  # 非 JSON
        result = extract_create_params("记一个开会")
        self.assertIsNone(result)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_extractor.py -v`

Expected: `ModuleNotFoundError: No module named 'smart_assistant.extractors.memo_extractor'`

- [ ] **Step 3: 写实现文件**

```python
"""smart_assistant.extractors.memo_extractor — 备忘录创建的 LLM 提取器

LLM 解析"中文 query → CreateParams",失败兜底为 None(由调用方
返回 found=False,不降级到规则)。

鲁棒性:
- LLM 不可用 / 抛异常 → None
- LLM 返回非 JSON 文本 → 用正则提取首个 {…} 块再试
- 解析后必填字段(title)缺失 → None

参考 smart_assistant.extractors.swap_extractor 的同款 stub 接口。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date as date_cls
from typing import Optional

from .prompts.memo_create_prompt import (
    MEMO_CREATE_SYSTEM_PROMPT,
    build_create_user_prompt,
)

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class CreateParams:
    """备忘录创建参数(从 query 提取)"""

    title: str
    content: str = ""
    reminder_time: Optional[str] = None  # ISO 8601 字符串


def _call_llm(query: str) -> Optional[str]:
    """调用 LLM 抽取参数,失败兜底 None。

    注:stub 接口,生产代码接入 LLM 路由在 Task 3 dry_run 路径调用方注入;
    本单元测试直接 patch 此函数,无需 mock LLM 路由层。
    """
    try:
        from llm_service.router import get_router

        today_str = date_cls.today().isoformat()
        prompt = build_create_user_prompt(query, today_str)
        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=prompt,
            system_message=MEMO_CREATE_SYSTEM_PROMPT,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning("memo_extractor._call_llm 失败: %s", e)
        return None


def _extract_json_block(text: str) -> str | None:
    """从 LLM 输出里用正则抓首个 {…} JSON 块,失败 None。"""
    match = re.search(r"\{[\s\S]*?\}", text)
    return match.group(0) if match else None


def _call_llm_with_today(query: str, today_str: str) -> str | None:
    """测试注入 today_str 的入口(避免单测依赖 date.today)。"""
    try:
        from llm_service.router import get_router

        prompt = build_create_user_prompt(query, today_str)
        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=prompt,
            system_message=MEMO_CREATE_SYSTEM_PROMPT,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning("memo_extractor._call_llm_with_today 失败: %s", e)
        return None


def extract_create_params(query: str, today_str: str | None = None) -> CreateParams | None:
    """从自然语言 query 抽取 CreateParams。失败返回 None。

    Args:
        query: 用户的自然语言
        today_str: 可选 ISO 字符串(YYYY-MM-DD),供单测注入;
                  默认 None → _call_llm 内部用今日日期

    Returns:
        CreateParams | None
    """
    raw = _call_llm(query) if today_str is None else _call_llm_with_today(query, today_str)
    if raw is None:
        return None

    json_text = _extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_extractor JSON 解析失败: %s", json_text[:200])
        return None

    title = (data.get("title") or "").strip()
    if not title:
        return None

    reminder = data.get("reminder_time")
    if reminder in (None, "", "null"):
        reminder = None

    return CreateParams(
        title=title[:200],  # 防御性 truncate 到模型字段上限
        content=(data.get("content") or "").strip(),
        reminder_time=reminder if isinstance(reminder, str) else None,
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_extractor.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tests/test_memo_extractor.py omni_desk_backend/smart_assistant/extractors/memo_extractor.py
git commit -m "feat(smart-assistant): add memo create LLM extractor"
```

---

## Task 3: MemoCreateTool 写失败测试

**Files:**
- Create: `omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py`

**Interfaces:**
- 测试目标:`smart_assistant.tools.memo_write_tools.MemoCreateTool`
- Consumes: 之后 Task 4 写的 `MemoCreateTool`
- 不写实现,只写测试用例(7 个,见下)。

- [ ] **Step 1: 写测试文件**

```python
"""MemoCreateTool 单元测试(dry_run + confirmed + 拒认二次确认外路径)。
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools import MemoCreateTool

User = get_user_model()


class TestMemoCreateToolRegistry(TestCase):
    def test_tool_name(self):
        self.assertEqual(MemoCreateTool().name, "memo_create")

    def test_tool_intent_type(self):
        self.assertEqual(MemoCreateTool().intent_type, "memo_create")

    def test_tool_risk_level_is_write(self):
        self.assertEqual(MemoCreateTool().risk_level, "write")

    def test_tool_requires_confirmation(self):
        self.assertTrue(MemoCreateTool().require_confirmation)


class TestMemoCreateToolDryRun(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.tool = MemoCreateTool()

    def test_dry_run_returns_draft(self):
        ctx = {
            "dry_run": True,
            "user": self.user,
            "query": "提醒明天下午3点开会",
        }
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            from smart_assistant.extractors.memo_extractor import CreateParams

            mock_extract.return_value = CreateParams(
                title="开会", content="季度总结", reminder_time=None
            )
            result = self.tool.execute(query="提醒明天下午3点开会", ctx=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
        self.assertEqual(result["draft"]["fields"]["title"], "开会")

    def test_dry_run_returns_not_found_when_extractor_fails(self):
        ctx = {"dry_run": True, "user": self.user, "query": "ssss"}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = None
            result = self.tool.execute(query="ssss", ctx=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolConfirmed(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="x")
        self.tool = MemoCreateTool()

    def test_confirmed_persists_memo(self):
        from memos.models import Memo

        ctx = {"confirmed": True, "user": self.user, "query": "记一条备忘"}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            from smart_assistant.extractors.memo_extractor import CreateParams

            mock_extract.return_value = CreateParams(
                title="买菜", content="番茄 鸡蛋", reminder_time=None
            )
            result = self.tool.execute(query="记一条备忘", ctx=ctx)
        self.assertTrue(result["found"])
        memo = Memo.objects.get(id=result["result"]["memo_id"])
        self.assertEqual(memo.user, self.user)
        self.assertEqual(memo.title, "买菜")
        self.assertFalse(memo.is_completed)

    def test_confirmed_missing_user_returns_not_found(self):
        ctx = {"confirmed": True, "user": None, "query": "记"}
        result = self.tool.execute(query="记", ctx=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolFallbackPath(TestCase):
    """未带 dry_run / confirmed 标记的兜底路径(防御,理论上不到)。"""

    def test_fallback_returns_error(self):
        from django.contrib.auth.models import AnonymousUser

        tool = MemoCreateTool()
        ctx = {"user": AnonymousUser(), "query": "x"}
        result = tool.execute(query="x", ctx=ctx)
        self.assertFalse(result["found"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py -v`

Expected: `ModuleNotFoundError: No module named 'smart_assistant.tools.memo_write_tools'`

---

## Task 4: MemoCreateTool 实现

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/memo_write_tools.py`

**Interfaces:**
- Consumes:
  - `smart_assistant.tools.base.BaseTool`
  - `smart_assistant.extractors.memo_extractor.extract_create_params`
  - `memos.models.Memo`
- Produces:
  - `class MemoCreateTool(BaseTool)`,`name="memo_create"`,`intent_type="memo_create"`,`risk_level="write"`,`require_confirmation=True`
  - `execute(query=None, ctx=None, **kwargs) -> dict` — 内部根据 `ctx["dry_run"]` / `ctx["confirmed"]` 分支

- [ ] **Step 1: 写实现文件**

```python
"""smart_assistant.tools.memo_write_tools — 备忘录写工具(PR1:create)

PR1 范围:仅 MemoCreateTool。PR2 在新文件 memo_write_tools_v2.py(避免破坏 PR1 评审闭环)
补 MemoUpdateTool / MemoDeleteTool;文件名待 PR2 plan 决定(可能拆/合)。

业务逻辑复用 memos.Memo 模型,通过 ORM 直接 create,跳过 MemoViewSet
(后者面向 HTTP,工具层走 ORM 更轻便)。
工具层只负责:
1. 自然语言解析(query → CreateParams)
2. dry_run 模式下返回 draft(供 confirm-replay 框架存缓存)
3. confirmed 模式下调用业务逻辑落库

上游依赖:
- confirm-replay 框架:Reference docs/plans/2026-08-04_sa-confirm-framework.md
- smart_assistant.extractors.memo_extractor.extract_create_params(LLM 解析)
- memos.models.Memo(数据落库目标)
"""
from __future__ import annotations

from django.db import transaction

from .base import BaseTool
from ..extractors.memo_extractor import extract_create_params
from memos.models import Memo

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


class MemoCreateTool(BaseTool):
    """基于自然语言创建备忘录(write, require_confirmation=True)

    复用 confirm-replay 框架:dry_run → 用户确认 → confirmed 落库。
    """

    name = "memo_create"
    description = "基于自然语言创建一条备忘录/便签(支持设置提醒时间)"
    intent_type = "memo_create"
    risk_level = "write"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 创建备忘录。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言创建一条备忘录/便签(写操作,需要用户确认)。"
                    "dry_run 返回 draft,用户确认后真正落库。"
                    "示例 query: '帮我记一条下午开会的备忘'、"
                    "'提醒明天早上 9 点提交周报'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含标题/内容/可选提醒时间",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, ctx=None, **kwargs) -> dict:
        """执行备忘录创建(双调用模式:dry_run / confirmed)。"""
        ctx_dict = ctx if isinstance(ctx, dict) else {}

        if ctx_dict.get("dry_run"):
            return self._dry_run(query, ctx_dict)

        if ctx_dict.get("confirmed"):
            return self._confirmed(query, ctx_dict)

        # 兜底(理论上不可达:orchestrator 会拦截)
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _dry_run(self, query, ctx) -> dict:
        user = ctx.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录"}

        params = extract_create_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别备忘内容,请明确想记什么"}

        draft = {
            "summary": f"将创建备忘录: 《{params.title}》",
            "fields": {
                "title": params.title,
                "content": params.content,
                "reminder_time": params.reminder_time,
            },
        }
        if params.reminder_time:
            draft["summary"] += f", 提醒时间 {params.reminder_time}"

        return {"found": True, "draft": draft}

    def _confirmed(self, query, ctx) -> dict:
        user = ctx.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录"}

        params = extract_create_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别备忘内容"}

        try:
            with transaction.atomic():
                memo = Memo.objects.create(
                    user=user,
                    title=params.title,
                    content=params.content,
                    reminder_time=params.reminder_time or None,
                )
        except Exception as e:
            logger.warning("memo_create 落库失败: %s", e)
            return {"found": False, "message": f"创建备忘录失败: {e!s}"}

        logger.info(
            "memo_create.persisted",
            extra={
                "event": "memo_create.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )

        return {
            "found": True,
            "result": {
                "memo_id": memo.id,
                "title": memo.title,
                "reminder_time": str(memo.reminder_time) if memo.reminder_time else None,
            },
            "summary": f"已创建备忘录《{memo.title}》",
        }

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet(跨模块汇总路径使用)。"""
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录。"""
        return qs.filter(user=ctx.user)
```

- [ ] **Step 2: 跑测试确认全部通过**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py omni_desk_backend/smart_assistant/tests/test_memo_extractor.py -v`

Expected: 10 passed(7 + 3)

- [ ] **Step 3: 运行全量 smart_assistant 测试,确认无回归**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/ -v --tb=short -x`

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py omni_desk_backend/smart_assistant/tools/memo_write_tools.py
git commit -m "feat(smart-assistant): add MemoCreateTool with confirm-replay"
```

---

## Task 5: Apps.py 注册 MemoCreateTool

**Files:**
- Modify: `omni_desk_backend/smart_assistant/apps.py`(在 `ToolRegistry.register(MemoTool())` 后追加一行)

**Interfaces:**
- Consumes: `smart_assistant.tools.memo_write_tools.MemoCreateTool`
- Produces: `apps.py:ready()` 多一行 `from .tools.memo_write_tools import MemoCreateTool` 与 `ToolRegistry.register(MemoCreateTool())`

- [ ] **Step 1: 修改 apps.py**

在第 19 行 `from .tools.memo_tool import MemoTool` 之下新增一行 `from .tools.memo_write_tools import MemoCreateTool`,然后在第 41 行 `ToolRegistry.register(MemoTool())` 之后追加一行 `ToolRegistry.register(MemoCreateTool())`。

- [ ] **Step 2: 重跑注册相关测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/ -v -k "test_tools or test_registry or test_assert" --tb=short`

Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add omni_desk_backend/smart_assistant/apps.py
git commit -m "feat(smart-assistant): register MemoCreateTool in apps.ready()"
```

---

## Task 6: prompt_builder 增补 memo_create 意图

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/prompt_builder.py`

**Interfaces:**
- Consumes: 既有 `INTENT_PROMPT`
- Produces: `INTENT_PROMPT` 模板内追加一行

- [ ] **Step 1: 在 `INTENT_PROMPT` 中,line 69 之后追加**

(在已有 "如果用户的问题与备忘录、便签查询相关,返回 memo_query" 那一行后追加)

```
如果用户的问题与创建备忘录、新增便签、设置提醒相关,返回 memo_create
```

- [ ] **Step 2: 跑相关测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/ -v -k "prompt_builder or intent" --tb=short`

Expected: 没有 prompt_builder 直接单测时,这一步以"全量测试不退步"为合格

- [ ] **Step 3: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/prompt_builder.py
git commit -m "feat(smart-assistant): add memo_create intent hint to INTENT_PROMPT"
```

---

## Task 7: tool_chain_planner 增补 memo_create 关键字

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/tool_chain_planner.py`

**Interfaces:**
- Consumes: `intent_keywords` 字典 (line 57-66)
- Produces: 增加 `"memo_create": ["建一条", "创建备忘", "新增备忘", "记一条", "提醒我", "记一下"]`

- [ ] **Step 1: 在 `intent_keywords` 字典 line 63 后追加**

```python
        "memo_create": ["建一条", "创建备忘", "新增备忘", "记一条", "提醒我", "记一下"],
```

- [ ] **Step 2: 跑 tool_chain_planner 测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/ -v -k "chain" --tb=short`

Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/tool_chain_planner.py
git commit -m "feat(smart-assistant): add memo_create keywords to chain planner"
```

---

## Task 8: Docs 增补(PR1 范围最小)

**Files:**
- Modify: `docs/technical/16-smart-assistant.md`

**Interfaces:**
- Produces: §2.2 工具表新增 `MemoCreateTool` 条目一行

- [ ] **Step 1: 在 docs/technical/16-smart-assistant.md 工具表(line 79 附近)追加一行**

```
| `MemoCreateTool` | 创建备忘录(写, 需确认) | `memos.Memo` |
```

(PR3 docs 计划会进一步扩展用户手册双向链接)

- [ ] **Step 2: Commit**

```bash
git add docs/technical/16-smart-assistant.md
git commit -m "docs(smart-assistant): document MemoCreateTool"
```

---

## Task 9: 合并与提 PR(PR1)

**Files:** 无新代码改动

- [ ] **Step 1: 确认分支与工作区干净**

Run: `git status`

Expected: 分支 `feat/memo-create-tool`,无未提交改动

- [ ] **Step 2: 重跑全量 smart_assistant 测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/ --tb=short -q`

Expected: 全部通过,零回归

- [ ] **Step 3: 重跑 lint(mypy / ruff)**

Run:
```bash
conda run -n OmniDesk ruff check omni_desk_backend/smart_assistant/tools/memo_write_tools.py omni_desk_backend/smart_assistant/extractors/memo_extractor.py omni_desk_backend/smart_assistant/extractors/prompts/memo_create_prompt.py
conda run -n OmniDesk mypy omni_desk_backend/smart_assistant/tools/memo_write_tools.py omni_desk_backend/smart_assistant/extractors/memo_extractor.py 2>&1 | head -40
```

Expected: 0 errors(mypy 项目 CI 用宽松模式)

- [ ] **Step 4: 推到远端并开 PR**

```bash
git push -u origin feat/memo-create-tool
gh pr create \
  --title "feat(smart-assistant): MemoCreateTool — 对话式创建备忘录" \
  --body "## 背景
智能助手工具链上备忘录功能长期停留在'只读查询'(MemoTool),文档与实现脱节:
BaseTool.risk_level 文档明确说'write 工具的典型例子是新建日程、更新备忘录',
但实际没有 create/update/delete 实现。

## 本 PR(PR1)范围
- 新增 MemoCreateTool (write, require_confirmation=True)
- 复用 SwapRequestCreateTool 的 dry_run → confirmed 双调用模式 + confirm-replay 框架
- extractors/memo_extractor.py:LLM 提取 title/content/reminder_time
- INTENT_PROMPT / _matches_intent 增补 memo_create
- apps.py 注册

## 后续
PR2: MemoUpdateTool + MemoDeleteTool(destructive + confirm)
PR3: 文档同步(11-memo-system.md 与 16-smart-assistant.md 双向链接 + 用户手册更新)

## 测试
10 个新单测(memo_extractor 3 个 + memo_create_tool 7 个),pytest 全量回归通过。"
```

- [ ] **Step 5: 监控 CI**

Run: `gh pr checks <PR_NUMBER> --watch`

Expected: 全部 CI 工作绿;若红则 STOP,报告用户"CI 红了,要修吗?" — **不自动修**

- [ ] **Step 6: 用户 merge 后清理**

```bash
git switch main
git pull --rebase origin main
git branch -d feat/memo-create-tool
git push origin --delete feat/memo-create-tool
```

---

## Spec Coverage(自检:每条 spec 都有 task 对应)

| 优化项 | 对应 Task |
|---|---|
| MemoCreateTool(write, confirm) | Task 4(实现)+ Task 3(测试)+ Task 5(注册) |
| extractor LLM 解析 + 失败兜底 | Task 2(主体 + 测试)+ Task 1(prompt 模板) |
| prompt_builder.intent 增补 | Task 6 |
| tool_chain_planner 关键字增补 | Task 7 |
| 文档同步(最小,只 doc 增量) | Task 8 |
| 提 PR | Task 9 |

**不在 PR1 范围**(由 PR2 / PR3 兜底):
- MemoUpdateTool / MemoDeleteTool → PR2 独立 plan
- 备忘录到点提醒(P1 提醒通道)→ PR3 或后续 plan
- office_assistant 联动 → 后续 plan
- priority / recurrence 字段 → DB schema 改动,需独立 spec 评估

---

## Placeholder Scan(自检)

- ✅ 无 "TBD" / "TODO" / "fill in later"
- ✅ 无 "类似 Task N" 跨引用 — 每个 task 内容独立可读
- ✅ 无 "Add appropriate error handling" 空话 — Task 4 的 `_dry_run` / `_confirmed` 都有显式 try/except 与 found=False 返回
- ✅ 所有 type/method 签名在不同 task 间一致:
  - `extract_create_params(query, today_str=None) -> CreateParams | None`
  - `MemoCreateTool().execute(query, ctx) -> dict`

---

## 与项目规则的兼容性

- ✅ 走 CLAUDE.md Plan-First 流程:本文档即 `docs/plans/2026-08-13_memo-write-tools.md`
- ✅ 走 git-workflow.md 流程:feature 分支(feat/memo-create-tool)→ push → PR → CI 绿 → 用户 merge → 清理
- ✅ 走 testing.md:10 个新单测,dry_run / confirmed / 失败三条路径全覆盖
- ✅ 走 security.md:无硬编码密钥,ToolContext.user 来自 JWT 中间件
- ✅ 走 code-review.md checklist:函数 <50 行,文件 <800 行
- ✅ 走 development-workflow.md §0(研究复用):Task 4 直接 align `SwapRequestCreateTool._dry_run/_confirmed` 模式
- ✅ 走 coding-style.md:无 mutation,函数 <50 行,无 magic number
- ✅ 走 language.md:commit / PR 描述走中文

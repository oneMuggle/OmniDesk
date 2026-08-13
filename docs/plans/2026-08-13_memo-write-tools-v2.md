# Memo 写工具 PR2:Update + Delete 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐备忘录写工具集 —— `MemoUpdateTool`(write, 需确认)+ `MemoDeleteTool`(destructive, 需确认),复用 PR1 的 confirm-replay 模式;并根治 PR1 遗留的框架级 user 注入 gap(I1)、keyword 子串重叠、naive datetime RuntimeWarning、mypy 2 错、LLM 调用重复。

**Architecture:** 与 PR1 完全一致的 `dry_run → confirmed` 双调用模式。两个新工具放新文件 `memo_write_tools_v2.py`(PR1 已预留名称,避免破坏 PR1 评审闭环),共享 `_parse_reminder_time`。定位目标备忘录采用「LLM 提取标题关键词 → `user` + `title__icontains` 匹配」策略,dry_run 时多候选直接拒绝(防误改/误删),draft fields 携带 `memo_id` + `target_title`,confirmed 时按 `memo_id`(校验 user 归属)优先定位、回退标题重定位。框架根治在 orchestrator legacy/SSE 两处 dry_run context 补 `user` 注入(与 native 路径 C-2 对齐)。

**Tech Stack:** Django 4.2 / smart_assistant / confirm-replay 框架 / llm_service.router

## Global Constraints

- **工具契约**:所有新工具 `execute(self, query=None, context=None, **kwargs) -> dict`,框架所有调用点以 `context=` 关键字传参;context 为 dict(含 `dry_run`/`confirmed`/`user`/`draft`)或 ToolContext 实例(仅 user 兜底)。
- **失败契约**:失败一律返回 `{"found": False, "message": "<中文>"}`,不抛异常(DB 异常捕获转 found=False)。
- **risk_level 语义**:`MemoUpdateTool` = `"write"` + `require_confirmation=True`;`MemoDeleteTool` = `"destructive"` + `require_confirmation=True`(BaseTool 文档强制 destructive 必须确认;这是注册表中第一个 destructive 工具,Registry risk_order 已支持自动排序)。
- **draft 格式**:`{"summary": str, "fields": {…}}`;chat.py replay 注入 `draft_entry.get("draft", {}).get("fields")` → 工具 confirmed 优先读 `ctx["draft"]`,缺失回退 LLM。
- **定位安全**:update/delete 必须校验 `user` 归属(`Memo.objects.filter(user=user)`);多候选(dry_run 时 >1 条匹配)一律拒绝。
- **计数断言同步**:注册工具后 `tests/test_check_tool_scopes_cmd.py:110` 断言 `"20"` → `"21"` → `"22"`(每注册一个同步一次,避免 T5 回归重演)。`test_openai_tool_schemas.py` 用 `_collect_all_tools()` 动态收集,新工具自动覆盖,仅 docstring 计数顺带更新。
- **代码卫生**:`ruff check omni_desk_backend/` + `ruff format --check` 必须全绿(CI 阻塞);mypy 为 continue-on-error(不阻塞,但 Task 8 顺带修 PR1 遗留 2 错)。
- **测试命令**:`conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/ -q`(pytest.ini 已设 test settings)。
- **日志**:`logger.<level>("event", extra={"event": "memo_<action>.<state>", ...})`。
- **中文**:代码注释、commit message、PR description 全中文(代码标识符除外)。
- **分支**:`feat/memo-update-delete-tool`(基于 main,PR1 已合并)。merge 策略 squash merge,PR 必须注明本文档 Task 6 的 I1 根治。

---

### Task 0: 建分支

**Files:**
- (无代码)

- [ ] **Step 1: 建分支**

```bash
git switch main && git pull --rebase origin main
git switch -c feat/memo-update-delete-tool
```

Expected: 分支基于最新 main(含 PR1 的 1de59b01)。

---

### Task 1: 共享 LLM helper + create extractor 消重(T2-1)

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/llm_helpers.py`
- Modify: `omni_desk_backend/smart_assistant/extractors/memo_extractor.py`(合并 `_call_llm` / `_call_llm_with_today`)

**Interfaces:**
- Produces: `llm_helpers.call_extractor_llm(system_prompt: str, user_prompt: str) -> str | None`;`llm_helpers.extract_json_block(text: str) -> str | None` —— Task 2/4 的 update/delete extractor 复用。
- Consumes: `llm_service.router.get_router(app_name="smart_assistant").generate(...)`(现有调用形态)。

- [ ] **Step 1: 创建 `llm_helpers.py`**

```python
"""smart_assistant.extractors.llm_helpers — extractor 共享 LLM 调用助手

封装三类 memo extractor(create/update/delete)共用的:
- LLM 路由调用(失败兜底 None)
- JSON 块提取(LLM 输出非纯 JSON 时用正则抓首个 {…} 块)

失败路径全部返回 None,由各 extractor 决定降级策略。
"""

from __future__ import annotations

import re

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def call_extractor_llm(system_prompt: str, user_prompt: str) -> str | None:
    """调用 LLM 路由,失败返回 None(不抛异常)。"""
    try:
        from llm_service.router import get_router

        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=user_prompt,
            system_message=system_prompt,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning("smart_assistant.llm_helpers.call_failed", extra={
            "event": "smart_assistant.llm_helpers.call_failed",
            "error": str(e),
        })
        return None


def extract_json_block(text: str) -> str | None:
    """从 LLM 输出里用正则抓首个 {…} JSON 块,失败 None。"""
    match = re.search(r"\{[\s\S]*?\}", text)
    return match.group(0) if match else None
```

- [ ] **Step 2: 重构 `memo_extractor.py` 合并 `_call_llm`**

替换原 `_call_llm(query)` + `_call_llm_with_today(query, today_str)` 两个函数为单个:

```python
def _call_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_CREATE_SYSTEM_PROMPT,
        build_create_user_prompt(query, today_str),
    )
```

同时删掉 `_extract_json_block` 函数体改为委托(保留函数名避免外部引用断裂):

```python
def _extract_json_block(text: str) -> str | None:
    """兼容入口:委托 llm_helpers.extract_json_block。"""
    return extract_json_block(text)
```

`extract_create_params` 内调用改为 `raw = _call_llm(query, today_str)`(today_str=None 时自动今日)。

- [ ] **Step 3: 跑回归**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_extractor.py -v --tb=short`

Expected: 3 passed(测试 mock `memo_extractor._call_llm`,签名不变不受影响)。

- [ ] **Step 4: ruff 校验 + Commit**

```bash
cd omni_desk_backend && ruff check smart_assistant/extractors/ && ruff format smart_assistant/extractors/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/extractors/llm_helpers.py omni_desk_backend/smart_assistant/extractors/memo_extractor.py
git commit -m "refactor(smart-assistant): dedupe extractor LLM call via shared helper"
```

---

### Task 2: memo_update_extractor(prompt + extractor + 测试)

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/memo_update_prompt.py`
- Create: `omni_desk_backend/smart_assistant/extractors/memo_update_extractor.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_memo_update_extractor.py`

**Interfaces:**
- Consumes: `llm_helpers.call_extractor_llm` + `llm_helpers.extract_json_block`(Task 1)。
- Produces: `UpdateParams` dataclass(`target_title: str` / `new_title: str | None = None` / `new_content: str | None = None` / `new_reminder_time: str | None = None`);`extract_update_params(query, today_str=None) -> UpdateParams | None` —— Task 3 的 MemoUpdateTool 使用。

- [ ] **Step 1: 创建 `memo_update_prompt.py`**

```python
"""自然语言 → Memo 修改参数 LLM 提取 prompt 模板。"""

from __future__ import annotations

MEMO_UPDATE_SYSTEM_PROMPT = """你是 memo_update_extractor,负责把中文自然语言转换为备忘录修改参数。

用户会说类似"把明天开会的备忘改成后天下午3点"、"修改买菜备忘的标题为采购清单"。
请输出 JSON,字段:
- target_title: 要修改的备忘录标题(必填,用用户描述中的关键词,如"开会"、"买菜")
- new_title: 修改后的新标题(没有则省略或填 null)
- new_content: 修改后的新内容(没有则省略或填 null)
- new_reminder_time: 修改后的提醒时间,ISO 8601 格式 YYYY-MM-DDTHH:MM:SS(没有则省略或填 null)

规则:
- target_title 必须提取(用户提到的备忘录标题关键词)
- 至少一个 new_* 字段有值,否则视为无效
- 只输出 JSON,不要其他文字"""


def build_update_user_prompt(query: str, today_str: str) -> str:
    return f"当前日期: {today_str}\n用户请求: {query}\n\n请输出 JSON:"
```

- [ ] **Step 2: 创建 `memo_update_extractor.py`**

```python
"""smart_assistant.extractors.memo_update_extractor — 备忘录修改的 LLM 提取器

LLM 解析"中文 query → UpdateParams",失败兜底为 None(由调用方
返回 found=False)。校验:target_title 必填、至少一个 new_* 字段有值。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls

from .llm_helpers import call_extractor_llm, extract_json_block
from .prompts.memo_update_prompt import MEMO_UPDATE_SYSTEM_PROMPT, build_update_user_prompt

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class UpdateParams:
    """备忘录修改参数(从 query 提取)"""

    target_title: str
    new_title: str | None = None
    new_content: str | None = None
    new_reminder_time: str | None = None  # ISO 8601 字符串


def _call_update_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_UPDATE_SYSTEM_PROMPT,
        build_update_user_prompt(query, today_str),
    )


def extract_update_params(query: str, today_str: str | None = None) -> UpdateParams | None:
    """从自然语言 query 抽取 UpdateParams。失败返回 None。"""
    raw = _call_update_llm(query, today_str)
    if raw is None:
        return None

    json_text = extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_update_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_update_extractor JSON 解析失败: %s", json_text[:200])
        return None

    target = (data.get("target_title") or "").strip()
    if not target:
        return None

    new_title = (data.get("new_title") or "").strip() or None
    new_content = (data.get("new_content") or "").strip() or None
    reminder = data.get("new_reminder_time")
    if reminder in (None, "", "null"):
        reminder = None
    new_reminder_time = reminder if isinstance(reminder, str) else None

    if new_title is None and new_content is None and new_reminder_time is None:
        return None  # 未指定任何修改

    return UpdateParams(
        target_title=target[:200],  # 防御性 truncate 到模型字段上限
        new_title=new_title[:200] if new_title else None,
        new_content=new_content,
        new_reminder_time=new_reminder_time,
    )
```

- [ ] **Step 3: 创建 `test_memo_update_extractor.py`**

```python
"""MemoUpdateTool LLM extractor 单测(patch _call_update_llm)。"""
from unittest.mock import patch

from django.test import TestCase

from smart_assistant.extractors.memo_update_extractor import (
    UpdateParams,
    extract_update_params,
)


class TestExtractUpdateParams(TestCase):
    def test_parses_full_update(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = (
                '{"target_title": "开会", "new_title": "周会", '
                '"new_content": "季度总结", "new_reminder_time": "2026-08-14T15:00:00"}'
            )
            params = extract_update_params("把开会的备忘改成周会")
        self.assertIsInstance(params, UpdateParams)
        self.assertEqual(params.target_title, "开会")
        self.assertEqual(params.new_title, "周会")
        self.assertEqual(params.new_content, "季度总结")
        self.assertEqual(params.new_reminder_time, "2026-08-14T15:00:00")

    def test_returns_none_when_target_missing(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"new_title": "周会"}'
            params = extract_update_params("改标题")
        self.assertIsNone(params)

    def test_returns_none_when_no_changes(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"target_title": "开会"}'
            params = extract_update_params("把开会那天的备忘改一下")
        self.assertIsNone(params)

    def test_returns_none_when_llm_fails(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = None
            params = extract_update_params("改备忘")
        self.assertIsNone(params)
```

- [ ] **Step 4: 跑测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_update_extractor.py -v --tb=short`

Expected: 4 passed。

- [ ] **Step 5: ruff 校验 + Commit**

```bash
cd omni_desk_backend && ruff check smart_assistant/extractors/ && ruff format smart_assistant/extractors/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/extractors/prompts/memo_update_prompt.py omni_desk_backend/smart_assistant/extractors/memo_update_extractor.py omni_desk_backend/smart_assistant/tests/test_memo_update_extractor.py
git commit -m "feat(smart-assistant): add memo update LLM extractor"
```

---

### Task 3: MemoUpdateTool(测试先行 + 实现 + 注册)

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/memo_write_tools_v2.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_memo_update_tool.py`
- Modify: `omni_desk_backend/smart_assistant/apps.py`(注册)
- Modify: `omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py:110`(断言 20→21)

**Interfaces:**
- Consumes: `_parse_reminder_time`(from `.memo_write_tools`)、`extract_update_params`(Task 2)、`memos.models.Memo`。
- Produces: `MemoUpdateTool`(`name="memo_update"`, `intent_type="memo_update"`, `risk_level="write"`, `require_confirmation=True`)+ 模块级 `_find_candidates(user, target_title)` —— Task 5 的 MemoDeleteTool 复用 `_find_candidates`。

- [ ] **Step 1: 写失败测试 `test_memo_update_tool.py`(先 RED)**

```python
"""MemoUpdateTool 单元测试(dry_run + confirmed + 定位安全)。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools_v2 import MemoUpdateTool

User = get_user_model()


class TestMemoUpdateToolRegistry(TestCase):
    def test_tool_meta(self):
        tool = MemoUpdateTool()
        self.assertEqual(tool.name, "memo_update")
        self.assertEqual(tool.intent_type, "memo_update")
        self.assertEqual(tool.risk_level, "write")
        self.assertTrue(tool.require_confirmation)


class TestMemoUpdateToolDryRun(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="alice", password="x")
        self.memo = Memo.objects.create(user=self.user, title="明天开会", content="会议室A")
        self.tool = MemoUpdateTool()

    def test_dry_run_returns_draft_with_target(self):
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        ctx = {"dry_run": True, "user": self.user, "query": "把开会的备忘改成周会"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="开会", new_title="周会")
            result = self.tool.execute(query="把开会的备忘改成周会", context=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
        self.assertEqual(result["draft"]["fields"]["memo_id"], self.memo.id)
        self.assertEqual(result["draft"]["fields"]["new_title"], "周会")

    def test_dry_run_not_found_when_no_match(self):
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        ctx = {"dry_run": True, "user": self.user, "query": "把买菜备忘改一下"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="买菜", new_title="采购")
            result = self.tool.execute(query="把买菜备忘改一下", context=ctx)
        self.assertFalse(result["found"])
        self.assertIn("未找到", result["message"])

    def test_dry_run_rejects_multiple_candidates(self):
        from memos.models import Memo
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        Memo.objects.create(user=self.user, title="开会续会", content="x")
        ctx = {"dry_run": True, "user": self.user, "query": "把开会相关备忘改了"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="开会", new_title="周会")
            result = self.tool.execute(query="把开会相关备忘改了", context=ctx)
        self.assertFalse(result["found"])
        self.assertIn("找到", result["message"])

    def test_dry_run_missing_user_returns_not_found(self):
        ctx = {"dry_run": True, "user": None, "query": "改备忘"}
        result = self.tool.execute(query="改备忘", context=ctx)
        self.assertFalse(result["found"])


class TestMemoUpdateToolConfirmed(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="bob", password="x")
        self.other = User.objects.create_user(username="eve", password="x")
        self.memo = Memo.objects.create(user=self.user, title="买菜", content="番茄")
        self.other_memo = Memo.objects.create(user=self.other, title="买菜", content="别人的")
        self.tool = MemoUpdateTool()

    def test_confirmed_updates_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {
                "target_title": "买菜",
                "memo_id": self.memo.id,
                "new_title": "采购清单",
                "new_content": "番茄 鸡蛋",
                "new_reminder_time": None,
            },
        }
        result = self.tool.execute(query="把买菜备忘改成采购清单", context=ctx)
        self.assertTrue(result["found"])
        memo = Memo.objects.get(id=self.memo.id)
        self.assertEqual(memo.title, "采购清单")
        self.assertEqual(memo.content, "番茄 鸡蛋")

    def test_confirmed_does_not_touch_other_users_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {
                "target_title": "买菜",
                "memo_id": self.other_memo.id,  # 别人的 memo,归属校验应拒绝
                "new_title": "X",
            },
        }
        result = self.tool.execute(query="改备忘", context=ctx)
        self.assertFalse(result["found"])
        self.assertEqual(Memo.objects.get(id=self.other_memo.id).title, "买菜")

    def test_confirmed_draft_injection_skips_llm(self):
        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "买菜", "memo_id": self.memo.id, "new_title": "采购"},
        }
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            result = self.tool.execute(query="改备忘", context=ctx)
            mock_extract.assert_not_called()
        self.assertTrue(result["found"])
```

- [ ] **Step 2: 跑测试确认 RED**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_update_tool.py -v --tb=short`

Expected: `ModuleNotFoundError: No module named 'smart_assistant.tools.memo_write_tools_v2'`(工具文件尚不存在)。

- [ ] **Step 3: 创建 `memo_write_tools_v2.py`(MemoUpdateTool)**

```python
"""smart_assistant.tools.memo_write_tools_v2 — 备忘录写工具 v2(PR2:update + delete)

PR1 的 MemoCreateTool 在 memo_write_tools.py;PR2 新增 MemoUpdateTool /
MemoDeleteTool 放本文件(PR1 已预留文件名)。共享 _parse_reminder_time(from
memo_write_tools)与 _find_candidates(本文件模块级)。

定位策略:LLM 提取 target_title → user + title__icontains 匹配。
dry_run 多候选(>1 条)直接拒绝,防止误改/误删;draft fields 携带
memo_id + target_title,confirmed 按 memo_id(校验 user 归属)优先定位,
回退标题重定位。
"""

from __future__ import annotations

from django.db import transaction

from .base import BaseTool
from .memo_write_tools import _parse_reminder_time
from ..extractors.memo_update_extractor import UpdateParams, extract_update_params
from memos.models import Memo

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def _find_candidates(user, target_title: str):
    """按标题关键词返回用户名下的备忘录(创建时间倒序,取最近 5 条)。"""
    qs = Memo.objects.filter(user=user)
    if target_title:
        qs = qs.filter(title__icontains=target_title)
    return qs.order_by("-created_at")[:5]


class MemoUpdateTool(BaseTool):
    """基于自然语言修改一条已有备忘录(write, require_confirmation=True)。"""

    name = "memo_update"
    description = "基于自然语言修改一条已有备忘录/便签(支持改标题、内容、提醒时间)"
    intent_type = "memo_update"
    risk_level = "write"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言修改一条已有备忘录(写操作,需要用户确认)。"
                    "dry_run 返回 draft,用户确认后真正落库。"
                    "示例 query: '把明天开会的备忘改成后天下午3点'、"
                    "'修改买菜备忘的标题为采购清单'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含目标备忘录与要修改的内容",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}

        if ctx.get("dry_run"):
            return self._dry_run(query, ctx, context)

        if ctx.get("confirmed"):
            return self._confirmed(query, ctx, context)

        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _resolve_user(self, ctx, context):
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None:
            user = getattr(context, "user", None)
        return user

    def _resolve_params(self, query, ctx) -> UpdateParams | None:
        """优先使用框架注入的 draft fields,缺失时回退 LLM 提取。"""
        draft_fields = ctx.get("draft") if isinstance(ctx, dict) else None
        if isinstance(draft_fields, dict) and draft_fields.get("target_title"):
            return UpdateParams(
                target_title=draft_fields.get("target_title"),
                new_title=draft_fields.get("new_title"),
                new_content=draft_fields.get("new_content"),
                new_reminder_time=draft_fields.get("new_reminder_time"),
            )
        return extract_update_params(query or "")

    def _dry_run(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法修改备忘录(上下文缺失 user)"}

        params = extract_update_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别要修改的备忘录或修改内容"}

        if params.new_reminder_time and _parse_reminder_time(params.new_reminder_time) is None:
            return {"found": False, "message": f"无法解析提醒时间 '{params.new_reminder_time}'"}

        candidates = list(_find_candidates(user, params.target_title))
        if not candidates:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}
        if len(candidates) > 1:
            return {"found": False, "message": f"找到 {len(candidates)} 条匹配的备忘录,请指明更精确的标题"}

        memo = candidates[0]
        changes = []
        if params.new_title:
            changes.append(f"标题→{params.new_title}")
        if params.new_content:
            changes.append(f"内容→{params.new_content}")
        if params.new_reminder_time:
            changes.append(f"提醒→{params.new_reminder_time}")

        draft = {
            "summary": f"将修改备忘录《{memo.title}》: " + "、".join(changes),
            "fields": {
                "target_title": params.target_title,
                "memo_id": memo.id,
                "new_title": params.new_title,
                "new_content": params.new_content,
                "new_reminder_time": params.new_reminder_time,
            },
        }
        return {"found": True, "draft": draft}

    def _locate(self, user, params, fields) -> Memo | None:
        """优先按 draft 的 memo_id(校验 user 归属),回退按 target_title 重定位。"""
        memo_id = fields.get("memo_id") if isinstance(fields, dict) else None
        if memo_id is not None:
            memo = Memo.objects.filter(id=memo_id, user=user).first()
            if memo is not None:
                return memo
        candidates = list(_find_candidates(user, params.target_title))
        if len(candidates) != 1:
            return None
        return candidates[0]

    def _confirmed(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法修改备忘录(上下文缺失 user)"}

        params = self._resolve_params(query, ctx)
        if params is None:
            return {"found": False, "message": "无法识别要修改的备忘录"}

        memo = self._locate(user, params, ctx.get("draft") if isinstance(ctx, dict) else {})
        if memo is None:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}

        try:
            with transaction.atomic():
                if params.new_title is not None:
                    memo.title = params.new_title[:200]
                if params.new_content is not None:
                    memo.content = params.new_content
                if params.new_reminder_time is not None:
                    parsed = _parse_reminder_time(params.new_reminder_time)
                    if parsed is None:
                        return {"found": False, "message": f"无法解析提醒时间 '{params.new_reminder_time}'"}
                    memo.reminder_time = parsed
                memo.save(update_fields=["title", "content", "reminder_time", "updated_at"])
        except Exception as e:
            logger.warning(
                "memo_update.persist_failed",
                extra={
                    "event": "memo_update.persist_failed",
                    "user_id": getattr(user, "id", None),
                    "error": str(e),
                },
            )
            return {"found": False, "message": f"修改备忘录失败: {e!s}"}

        logger.info(
            "memo_update.persisted",
            extra={
                "event": "memo_update.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )
        return {
            "found": True,
            "result": {"memo_id": memo.id, "title": memo.title},
            "summary": f"已更新备忘录《{memo.title}》",
        }
```

- [ ] **Step 4: 跑测试确认 GREEN**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_update_tool.py -v --tb=short`

Expected: 8 passed。

- [ ] **Step 5: 注册 + 断言同步**

`apps.py` 在 `from .tools.memo_write_tools import MemoCreateTool` 之后加一行 `from .tools.memo_write_tools_v2 import MemoUpdateTool`;在 `ToolRegistry.register(MemoCreateTool())` 之后加 `ToolRegistry.register(MemoUpdateTool())`。

`test_check_tool_scopes_cmd.py:110` 断言 `"20"` → `"21"`,注释更新为 `21 = 13 基线 + 3 swap_request + 3 office/spreadsheet + MemoCreateTool + MemoUpdateTool`。

- [ ] **Step 6: 定向回归 + ruff + Commit**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py omni_desk_backend/smart_assistant/tests/test_memo_update_tool.py -v --tb=short`

Expected: 全过(check_tool_scopes 输出 21)。

```bash
cd omni_desk_backend && ruff check smart_assistant/ && ruff format smart_assistant/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/tools/memo_write_tools_v2.py omni_desk_backend/smart_assistant/tests/test_memo_update_tool.py omni_desk_backend/smart_assistant/apps.py omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py
git commit -m "feat(smart-assistant): add MemoUpdateTool with confirm-replay"
```

---

### Task 4: memo_delete_extractor(prompt + extractor + 测试)

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/memo_delete_prompt.py`
- Create: `omni_desk_backend/smart_assistant/extractors/memo_delete_extractor.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_memo_delete_extractor.py`

**Interfaces:**
- Consumes: `llm_helpers`(Task 1)。
- Produces: `DeleteParams` dataclass(`target_title: str`);`extract_delete_params(query, today_str=None) -> DeleteParams | None` —— Task 5 的 MemoDeleteTool 使用。

- [ ] **Step 1: 创建 `memo_delete_prompt.py`**

```python
"""自然语言 → Memo 删除参数 LLM 提取 prompt 模板。"""

from __future__ import annotations

MEMO_DELETE_SYSTEM_PROMPT = """你是 memo_delete_extractor,负责把中文自然语言转换为备忘录删除参数。

用户会说类似"删掉明天开会的备忘"、"把采购备忘删了"。
请输出 JSON,字段:
- target_title: 要删除的备忘录标题(必填,用用户描述中的关键词,如"开会"、"采购")

规则:
- target_title 必须提取
- 只输出 JSON,不要其他文字"""


def build_delete_user_prompt(query: str, today_str: str) -> str:
    return f"当前日期: {today_str}\n用户请求: {query}\n\n请输出 JSON:"
```

- [ ] **Step 2: 创建 `memo_delete_extractor.py`**

```python
"""smart_assistant.extractors.memo_delete_extractor — 备忘录删除的 LLM 提取器

LLM 解析"中文 query → DeleteParams",失败兜底为 None(由调用方
返回 found=False)。校验:target_title 必填。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls

from .llm_helpers import call_extractor_llm, extract_json_block
from .prompts.memo_delete_prompt import MEMO_DELETE_SYSTEM_PROMPT, build_delete_user_prompt

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class DeleteParams:
    """备忘录删除参数(从 query 提取)"""

    target_title: str


def _call_delete_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_DELETE_SYSTEM_PROMPT,
        build_delete_user_prompt(query, today_str),
    )


def extract_delete_params(query: str, today_str: str | None = None) -> DeleteParams | None:
    """从自然语言 query 抽取 DeleteParams。失败返回 None。"""
    raw = _call_delete_llm(query, today_str)
    if raw is None:
        return None

    json_text = extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_delete_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_delete_extractor JSON 解析失败: %s", json_text[:200])
        return None

    target = (data.get("target_title") or "").strip()
    if not target:
        return None

    return DeleteParams(target_title=target[:200])
```

- [ ] **Step 3: 创建 `test_memo_delete_extractor.py`**

```python
"""MemoDeleteTool LLM extractor 单测(patch _call_delete_llm)。"""
from unittest.mock import patch

from django.test import TestCase

from smart_assistant.extractors.memo_delete_extractor import (
    DeleteParams,
    extract_delete_params,
)


class TestExtractDeleteParams(TestCase):
    def test_parses_target(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"target_title": "开会"}'
            params = extract_delete_params("删掉开会的备忘")
        self.assertIsInstance(params, DeleteParams)
        self.assertEqual(params.target_title, "开会")

    def test_returns_none_when_target_missing(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"confirm": true}'
            params = extract_delete_params("删掉一个备忘")
        self.assertIsNone(params)

    def test_returns_none_when_llm_fails(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = None
            params = extract_delete_params("删备忘")
        self.assertIsNone(params)
```

- [ ] **Step 4: 跑测试 + ruff + Commit**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_delete_extractor.py -v --tb=short`

Expected: 3 passed。

```bash
cd omni_desk_backend && ruff check smart_assistant/extractors/ && ruff format smart_assistant/extractors/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/extractors/prompts/memo_delete_prompt.py omni_desk_backend/smart_assistant/extractors/memo_delete_extractor.py omni_desk_backend/smart_assistant/tests/test_memo_delete_extractor.py
git commit -m "feat(smart-assistant): add memo delete LLM extractor"
```

---

### Task 5: MemoDeleteTool(测试先行 + 实现 + 注册)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/memo_write_tools_v2.py`(追加 MemoDeleteTool)
- Create: `omni_desk_backend/smart_assistant/tests/test_memo_delete_tool.py`
- Modify: `omni_desk_backend/smart_assistant/apps.py`(注册)
- Modify: `omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py:110`(断言 21→22)

**Interfaces:**
- Consumes: `_find_candidates`(Task 3 模块级)、`extract_delete_params`(Task 4)。
- Produces: `MemoDeleteTool`(`name="memo_delete"`, `intent_type="memo_delete"`, `risk_level="destructive"`, `require_confirmation=True`)。

- [ ] **Step 1: 写失败测试 `test_memo_delete_tool.py`(先 RED)**

```python
"""MemoDeleteTool 单元测试(destructive + 定位安全 + 归属校验)。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools_v2 import MemoDeleteTool

User = get_user_model()


class TestMemoDeleteToolRegistry(TestCase):
    def test_tool_meta(self):
        tool = MemoDeleteTool()
        self.assertEqual(tool.name, "memo_delete")
        self.assertEqual(tool.intent_type, "memo_delete")
        self.assertEqual(tool.risk_level, "destructive")
        self.assertTrue(tool.require_confirmation)


class TestMemoDeleteToolDryRun(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="alice", password="x")
        self.memo = Memo.objects.create(user=self.user, title="旧采购单")
        self.tool = MemoDeleteTool()

    def test_dry_run_returns_draft_with_warning(self):
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        ctx = {"dry_run": True, "user": self.user, "query": "删掉旧采购单"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="采购")
            result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertTrue(result["found"])
        self.assertEqual(result["draft"]["fields"]["memo_id"], self.memo.id)
        self.assertIn("永久删除", result["draft"]["summary"])
        self.assertIn("不可恢复", result["draft"]["summary"])

    def test_dry_run_not_found(self):
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        ctx = {"dry_run": True, "user": self.user, "query": "删掉买菜备忘"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="买菜")
            result = self.tool.execute(query="删掉买菜备忘", context=ctx)
        self.assertFalse(result["found"])

    def test_dry_run_rejects_multiple_candidates(self):
        from memos.models import Memo
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        Memo.objects.create(user=self.user, title="采购清单 v2")
        ctx = {"dry_run": True, "user": self.user, "query": "删掉采购相关的"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="采购")
            result = self.tool.execute(query="删掉采购相关的", context=ctx)
        self.assertFalse(result["found"])

    def test_dry_run_missing_user_returns_not_found(self):
        ctx = {"dry_run": True, "user": None, "query": "删备忘"}
        result = self.tool.execute(query="删备忘", context=ctx)
        self.assertFalse(result["found"])


class TestMemoDeleteToolConfirmed(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="bob", password="x")
        self.other = User.objects.create_user(username="eve", password="x")
        self.memo = Memo.objects.create(user=self.user, title="旧采购单")
        self.other_memo = Memo.objects.create(user=self.other, title="旧采购单")
        self.tool = MemoDeleteTool()

    def test_confirmed_deletes_own_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "采购", "memo_id": self.memo.id},
        }
        result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertTrue(result["found"])
        self.assertFalse(Memo.objects.filter(id=self.memo.id).exists())

    def test_confirmed_does_not_delete_others_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "采购", "memo_id": self.other_memo.id},
        }
        result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertFalse(result["found"])
        self.assertTrue(Memo.objects.filter(id=self.other_memo.id).exists())

    def test_confirmed_not_found(self):
        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "不存在", "memo_id": 99999},
        }
        result = self.tool.execute(query="删掉不存在的", context=ctx)
        self.assertFalse(result["found"])
```

- [ ] **Step 2: 跑测试确认 RED**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_delete_tool.py -v --tb=short`

Expected: `AttributeError: module 'smart_assistant.tools.memo_write_tools_v2' has no attribute 'MemoDeleteTool'`。

- [ ] **Step 3: 追加 MemoDeleteTool 到 `memo_write_tools_v2.py`**

```python
class MemoDeleteTool(BaseTool):
    """基于自然语言删除一条已有备忘录(destructive, require_confirmation=True)。

    破坏性操作:draft summary 显式标注"永久删除 / 不可恢复",由 confirm-replay
    框架的二次确认承担用户确认。
    """

    name = "memo_delete"
    description = "基于自然语言删除一条已有备忘录/便签(破坏性操作,需二次确认)"
    intent_type = "memo_delete"
    risk_level = "destructive"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言删除一条已有备忘录(破坏性操作,必须用户二次确认)。"
                    "dry_run 返回 draft,用户确认后真正删除。"
                    "示例 query: '删掉明天开会的备忘'、'把采购备忘删了'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含要删除的备忘录标题关键词",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}

        if ctx.get("dry_run"):
            return self._dry_run(query, ctx, context)

        if ctx.get("confirmed"):
            return self._confirmed(query, ctx, context)

        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _resolve_user(self, ctx, context):
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None:
            user = getattr(context, "user", None)
        return user

    def _resolve_params(self, query, ctx):
        """优先使用框架注入的 draft fields,缺失时回退 LLM 提取。"""
        draft_fields = ctx.get("draft") if isinstance(ctx, dict) else None
        if isinstance(draft_fields, dict) and draft_fields.get("target_title"):
            from ..extractors.memo_delete_extractor import DeleteParams

            return DeleteParams(target_title=draft_fields.get("target_title"))
        return extract_delete_params(query or "")

    def _dry_run(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法删除备忘录(上下文缺失 user)"}

        params = extract_delete_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别要删除的备忘录"}

        candidates = list(_find_candidates(user, params.target_title))
        if not candidates:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}
        if len(candidates) > 1:
            return {"found": False, "message": f"找到 {len(candidates)} 条匹配的备忘录,请指明更精确的标题"}

        memo = candidates[0]
        draft = {
            "summary": f"⚠️ 将永久删除备忘录《{memo.title}》,此操作不可恢复。确认?",
            "fields": {"target_title": params.target_title, "memo_id": memo.id},
        }
        return {"found": True, "draft": draft}

    def _locate(self, user, params, fields) -> Memo | None:
        """优先按 draft 的 memo_id(校验 user 归属),回退按 target_title 重定位。"""
        memo_id = fields.get("memo_id") if isinstance(fields, dict) else None
        if memo_id is not None:
            memo = Memo.objects.filter(id=memo_id, user=user).first()
            if memo is not None:
                return memo
        candidates = list(_find_candidates(user, params.target_title))
        if len(candidates) != 1:
            return None
        return candidates[0]

    def _confirmed(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法删除备忘录(上下文缺失 user)"}

        params = self._resolve_params(query, ctx)
        if params is None:
            return {"found": False, "message": "无法识别要删除的备忘录"}

        memo = self._locate(user, params, ctx.get("draft") if isinstance(ctx, dict) else {})
        if memo is None:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}

        try:
            with transaction.atomic():
                memo.delete()
        except Exception as e:
            logger.warning(
                "memo_delete.persist_failed",
                extra={
                    "event": "memo_delete.persist_failed",
                    "user_id": getattr(user, "id", None),
                    "error": str(e),
                },
            )
            return {"found": False, "message": f"删除备忘录失败: {e!s}"}

        logger.info(
            "memo_delete.persisted",
            extra={
                "event": "memo_delete.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )
        return {
            "found": True,
            "result": {"memo_id": memo.id, "title": memo.title},
            "summary": f"已删除备忘录《{memo.title}》",
        }
```

同时文件顶部 import 补 `from ..extractors.memo_delete_extractor import extract_delete_params`。

- [ ] **Step 4: 跑测试确认 GREEN**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_delete_tool.py -v --tb=short`

Expected: 9 passed。

- [ ] **Step 5: 注册 + 断言同步**

`apps.py` 加 `from .tools.memo_write_tools_v2 import MemoUpdateTool, MemoDeleteTool`(合并为一行)+ `ToolRegistry.register(MemoDeleteTool())`。

`test_check_tool_scopes_cmd.py:110` 断言 `"21"` → `"22"`,注释更新为 `22 = 13 基线 + 3 swap_request + 3 office/spreadsheet + MemoCreateTool + MemoUpdateTool + MemoDeleteTool`。

- [ ] **Step 6: 定向回归 + ruff + Commit**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py omni_desk_backend/smart_assistant/tests/test_memo_delete_tool.py omni_desk_backend/smart_assistant/tests/test_tool_risk_level.py -v --tb=short`

Expected: 全过(输出 22;destructive 工具通过 risk_level 校验)。

```bash
cd omni_desk_backend && ruff check smart_assistant/ && ruff format smart_assistant/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/tools/memo_write_tools_v2.py omni_desk_backend/smart_assistant/tests/test_memo_delete_tool.py omni_desk_backend/smart_assistant/apps.py omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py
git commit -m "feat(smart-assistant): add MemoDeleteTool with confirm-replay (destructive)"
```

---

### Task 6: 框架 user 注入根治(I1)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:367`(legacy 同步 dry_run)
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:1372`(SSE 流式 dry_run)
- Modify: `omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py`(追加 legacy 形态测试)

**Interfaces:**
- 根治 PR1 final-review I1:`_legacy_process`(367)与 `process_stream`(1372)的 dry_run context 缺 `user`,导致默认(非 staff)用户走 legacy/SSE 路径时写工具 `_resolve_user` 拿不到 user → 功能不可用。与 native 路径 C-2(612-617,已含 `"user": getattr(context, "user", None)`)对齐。

- [ ] **Step 1: 修改 orchestrator.py:367**

将

```python
context={"history": conversation_history or [], "dry_run": True},
```

改为

```python
context={
    "history": conversation_history or [],
    "dry_run": True,
    "user": getattr(tool_context, "user", None),
},
```

- [ ] **Step 2: 修改 orchestrator.py:1372**

将

```python
context={"history": conversation_history or [], "dry_run": True},
```

改为

```python
context={
    "history": conversation_history or [],
    "dry_run": True,
    "user": getattr(tool_context, "user", None),
},
```

(两处字面相同,分别位于 `_legacy_process` 与 `process_stream`;`tool_context` 参数两函数都有,可能是 ToolContext 实例或 None,`getattr(..., None)` 对 None 安全。)

- [ ] **Step 3: 追加 legacy 形态回归测试到 `test_memo_create_tool.py`**

在 `TestMemoCreateToolContextContract` 内追加:

```python
    def test_legacy_style_dry_run_with_injected_user(self):
        """I1 根治后:legacy 路径 dry_run context 注入 user,工具可用(不再 found=False)。"""
        from smart_assistant.extractors.memo_extractor import CreateParams

        # 模拟 orchestrator 367 行修复后的 context(带 user,无 draft)
        ctx = {"history": [], "dry_run": True, "user": self.user}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = CreateParams(
                title="开会", content="下午3点", reminder_time=None
            )
            result = self.tool.execute(query="提醒明天下午3点开会", context=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
```

- [ ] **Step 4: 回归全量 smart_assistant 测试(重点 swap/office 写工具)**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py omni_desk_backend/smart_assistant/tests/ -k "swap or office or orchestrator or memo" --tb=short`

Expected: 全过 —— I1 修复只给 dry_run context 增加 user 键,swap/office 的 `_dry_run` 通过 `ctx.get("user")` 读取,修复后反而让它们 legacy 路径可用(行为改善,无回归)。

- [ ] **Step 5: ruff + Commit**

```bash
cd omni_desk_backend && ruff check smart_assistant/ && ruff format smart_assistant/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py
git commit -m "fix(smart-assistant): inject user into legacy/SSE dry_run context (I1)"
```

---

### Task 7: keyword 优先级 + 路由增补(memo_update/memo_delete)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/tool_chain_planner.py`(子串重叠消解 + intent_keywords 增补)
- Modify: `omni_desk_backend/smart_assistant/agent/prompt_builder.py`(INTENT_PROMPT 增补两行)
- Modify: `omni_desk_backend/smart_assistant/tests/test_tool_chain_planner.py`(追加重叠消解测试)

**Interfaces:**
- 根治 PR1 final-review T7:同一 query「提醒我明天开会」同时命中 `memo_query("提醒")` 与 `memo_create("提醒我")` → 误判多意图走 LLM plan(非确定性)。采用「子串覆盖消解」:短 keyword 命中被更长命中(且为其子串)覆盖。

- [ ] **Step 1: 重构 `tool_chain_planner.py` 的意图匹配**

在 `intent_keywords` 字典追加:

```python
        "memo_update": ["改备忘", "修改备忘", "更新备忘", "改提醒"],
        "memo_delete": ["删除备忘", "删掉备忘", "移除备忘", "清除备忘"],
```

将 `_matches_intent` 替换为返回命中 keyword 列表:

```python
def _matches_intent(query: str, schema: dict) -> list:
    """返回查询命中的 keyword 列表(空 = 不匹配)。

    返回 list 而非 bool,供 generate_tool_chain_plan 做子串重叠消解
    (短 keyword 命中被更长且包含它的命中覆盖)。
    """
    intent_name = schema.get("name", "").lower()
    keywords = intent_keywords.get(intent_name, [])
    return [kw for kw in keywords if kw in query]


def _resolve_intent_overlap(query: str, schemas: list) -> list:
    """消解 keyword 子串重叠后,返回匹配的意图名列表。

    规则:若命中 kw_a 是另一命中 kw_b 的严格子串(kw_a in kw_b 且不同),
    则 kw_a 的命中被覆盖丢弃。例:「提醒我明天开会」——
    memo_query 命中 "提醒"(2),memo_create 命中 "提醒我"(3);
    "提醒" in "提醒我" → memo_query 命中被覆盖,只剩 memo_create(单意图)。
    """
    hits = []  # [(intent, kw)]
    for schema in schemas:
        for kw in _matches_intent(query, schema):
            hits.append((schema["name"], kw))

    resolved: list = []
    seen: set = set()
    for name, kw in hits:
        covered = any(kw in other_kw and kw != other_kw for _, other_kw in hits)
        if covered or name in seen:
            continue
        seen.add(name)
        resolved.append(name)
    return resolved
```

`generate_tool_chain_plan` 中替换原 `relevant_tools` 构造:

```python
    # 检查查询中是否包含多个意图的关键词(子串重叠已消解)
    relevant_tools = _resolve_intent_overlap(query, schemas)
```

- [ ] **Step 2: INTENT_PROMPT 增补(prompt_builder.py)**

在 `如果用户的问题与创建备忘录、新增便签、设置提醒相关，返回 memo_create` 之后追加:

```
如果用户的问题与修改备忘录、更新便签、调整提醒相关，返回 memo_update
如果用户的问题与删除备忘录、移除便签相关，返回 memo_delete
```

- [ ] **Step 3: 测试重叠消解(追加到 `test_tool_chain_planner.py`)**

```python
class TestMemoKeywordOverlap(TestCase):
    """PR1 遗留:『提醒我』同时命中 memo_query(提醒)与 memo_create(提醒我)。"""

    def test_remind_me_is_single_intent(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [
            {"name": "memo_query"},
            {"name": "memo_create"},
            {"name": "memo_update"},
            {"name": "memo_delete"},
        ]
        result = _resolve_intent_overlap("提醒我明天开会", schemas)
        self.assertEqual(result, ["memo_create"])

    def test_remind_me_plus_schedule_is_multi_intent(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [
            {"name": "memo_query"},
            {"name": "memo_create"},
            {"name": "schedule_query"},
        ]
        result = _resolve_intent_overlap("提醒我开会和查明天排班", schemas)
        self.assertEqual(result, ["memo_create", "schedule_query"])

    def test_update_keyword_routes_to_update(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [{"name": "memo_query"}, {"name": "memo_create"}, {"name": "memo_update"}]
        # "改提醒" 是独立 token,不被 "提醒" 覆盖(反向),也不覆盖它
        result = _resolve_intent_overlap("把开会的备忘改提醒到后天", schemas)
        self.assertEqual(result, ["memo_update"])

    def test_delete_keyword_routes_to_delete(self):
        from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

        schemas = [{"name": "memo_query"}, {"name": "memo_delete"}]
        # "删除备忘" 含 "备忘",但 memo_query 无 "备忘" 精确命中其 keyword("备忘录"/"便签"/"提醒"),
        # 无重叠;结果唯一意图
        result = _resolve_intent_overlap("删除买菜备忘", schemas)
        self.assertEqual(result, ["memo_delete"])
```

注:`test_update_keyword_routes_to_update` 的 query「把开会的备忘改提醒到后天」:memo_update 命中 "改提醒"(3);memo_query 命中 "提醒"(2)且 "提醒" in "改提醒" → 被覆盖;memo_create 无命中。结果 `["memo_update"]`。✓

- [ ] **Step 4: 跑测试**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_tool_chain_planner.py -v --tb=short`

Expected: 全部通过(含新增 4 个重叠消解用例)。

- [ ] **Step 5: ruff + Commit**

```bash
cd omni_desk_backend && ruff check smart_assistant/ && ruff format smart_assistant/
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/agent/tool_chain_planner.py omni_desk_backend/smart_assistant/agent/prompt_builder.py omni_desk_backend/smart_assistant/tests/test_tool_chain_planner.py
git commit -m "fix(smart-assistant): resolve intent keyword substring overlap + route memo_update/delete"
```

---

### Task 8: 存量修复(M1 make_aware / M2 mypy / M4 格式容错)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/memo_write_tools.py`(3 处)

**Interfaces:**
- 修 PR1 final-review M1(naive datetime RuntimeWarning)、M2(mypy 2 错)、M4(提醒格式容错)。`_parse_reminder_time` 被 v2 文件共享,修复自动惠及 MemoUpdateTool/DeleteTool。

- [ ] **Step 1: M4 + M1 —— `_parse_reminder_time` 加 `%H:%M` 容错 + make_aware**

在 fmt 列表加 `"%Y-%m-%dT%H:%M"`(无秒),返回前 make_aware:

```python
def _parse_reminder_time(s: str) -> datetime | None:
    """鲁棒地解析提醒时间字符串,失败返回 None。

    接受格式:
    - "2026-08-12T15:00:00"(ISO datetime)
    - "2026-08-12T15:00"(ISO datetime 无秒)
    - "2026-08-12 15:00:00"(空格分隔)
    - "2026-08-12"(date-only,默认当日 00:00)

    返回 aware datetime(按 settings.TIME_ZONE),消除 USE_TZ=True 下
    落库 naive datetime 的 RuntimeWarning。
    """
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    else:
        logger.debug(
            "smart_assistant.memo_write_tools.reminder_time_parse_failed",
            extra={"event": "smart_assistant.memo_write_tools.reminder_time_parse_failed", "s": s},
        )
        return None
    from django.utils import timezone

    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
```

- [ ] **Step 2: M2a —— `_dry_run` 的 draft summary 拼接改为先构造再入 dict**

原代码(mypy:dict 值被推断为 `Collection[str]`,`+=` 报错):

```python
        draft = {
            "summary": f"将创建备忘录: 《{params.title}》",
            "fields": {...},
        }
        if params.reminder_time:
            draft["summary"] += f", 提醒时间 {params.reminder_time}"
```

改为:

```python
        summary = f"将创建备忘录: 《{params.title}》"
        if params.reminder_time:
            summary += f", 提醒时间 {params.reminder_time}"
        draft = {"summary": summary, "fields": {...}}
```

- [ ] **Step 3: M2b —— `_resolve_params` 的 title 加 isinstance 守卫**

原代码(mypy:`Any | None` 不兼容 `str`):

```python
        if isinstance(draft_fields, dict) and draft_fields.get("title"):
            return CreateParams(
                title=draft_fields.get("title"),
                ...
```

改为:

```python
        if isinstance(draft_fields, dict):
            title = draft_fields.get("title")
            if isinstance(title, str) and title:
                return CreateParams(
                    title=title,
                    content=draft_fields.get("content") or "",
                    reminder_time=draft_fields.get("reminder_time"),
                )
```

- [ ] **Step 4: 定向回归 + mypy 确认**

Run: `conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/tests/test_memo_create_tool.py -v --tb=short`

Expected: 8 passed(create 行为不变,仅内部实现)。

Run: `cd omni_desk_backend && mypy smart_assistant/tools/memo_write_tools.py smart_assistant/tools/memo_write_tools_v2.py 2>&1 | tail -5`

Expected: 不再报 `memo_write_tools.py` 的 `draft["summary"]` 与 `title=` 两错(CI mypy 为 continue-on-error,但本任务目标是消错)。

- [ ] **Step 5: ruff + Commit**

```bash
cd omni_desk_backend && ruff check smart_assistant/tools/memo_write_tools.py && ruff format smart_assistant/tools/memo_write_tools.py
cd /home/fz/project/OmniDesk
git add omni_desk_backend/smart_assistant/tools/memo_write_tools.py
git commit -m "fix(smart-assistant): make reminder_time aware + mypy fixes + %H:%M tolerance"
```

---

### Task 9: 文档 + 全量回归 + PR

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py`(docstring 计数 20→22,可选但建议)
- Modify: `docs/technical/16-smart-assistant.md`(§2.2 工具表增补两行)

**Interfaces:**
- 完成 PR2 交付:文档同步 + 全量验证 + 开 PR。

- [ ] **Step 1: §2.2 工具表增补**

在 `docs/technical/16-smart-assistant.md` §2.2 工具表 `| MemoCreateTool | 创建备忘录(写, 需确认) | memos.Memo |` 之后追加:

```
| `MemoUpdateTool` | 修改备忘录(写, 需确认) | `memos.Memo` |
| `MemoDeleteTool` | 删除备忘录(破坏性, 需确认) | `memos.Memo` |
```

头部计数"14 个"改"16 个"(以实际文件内容为准,只增不减)。

- [ ] **Step 2: 全量回归 + ruff 全量**

Run: `cd omni_desk_backend && ruff check . && ruff format --check .`

Expected: All checks passed + 349 files already formatted。

Run: `cd /home/fz/project/OmniDesk && conda run -n OmniDesk pytest omni_desk_backend/smart_assistant/ -q 2>&1 | tail -3`

Expected: 全量通过(此前 1322 passed;新增约 27 个用例)。覆盖率 ≥80%。

- [ ] **Step 3: Commit**

```bash
git add docs/technical/16-smart-assistant.md omni_desk_backend/smart_assistant/tests/test_openai_tool_schemas.py
git commit -m "docs(smart-assistant): document MemoUpdateTool/MemoDeleteTool"
```

- [ ] **Step 4: push + 开 PR**

```bash
git push -u origin feat/memo-update-delete-tool
gh pr create --title "feat(smart-assistant): 对话式修改/删除备忘录 MemoUpdateTool+MemoDeleteTool(PR2/3)" --body "..."
```

PR description 必须包含:
- 3 个工具现在全部可用(create + update + delete)
- **I1 根治说明**:legacy 同步 + SSE 两路径 dry_run context 已注入 user,非 staff 用户对话式写操作全部可用(swap/office 同步受益)
- keyword 重叠消解说明
- 测试计划(含 CI 绿后人工 merge)

- [ ] **Step 5: 监控 CI → 人工 merge → 清理**

```bash
gh pr checks <PR_NUMBER> --watch
```

CI 绿后报告用户 merge;merge 后:

```bash
git switch main && git pull --rebase origin main && git branch -d feat/memo-update-delete-tool
git push origin --delete feat/memo-update-delete-tool
```

---

## Spec Coverage(自检:每条需求都有 task 对应)

| 需求 | 对应 Task |
|---|---|
| MemoUpdateTool(write, confirm)+ 注册 + 断言同步 | Task 3 |
| MemoDeleteTool(destructive, confirm)+ 注册 + 断言同步 | Task 5 |
| update/delete LLM extractor(prompt + 解析 + 失败兜底) | Task 2 / Task 4 |
| 共享 LLM helper,create extractor 消重(T2-1) | Task 1 |
| 框架 user 注入根治(I1) | Task 6 |
| keyword 子串重叠消解 + memo_update/delete 路由 | Task 7 |
| naive datetime RuntimeWarning(M1)+ mypy 2 错(M2)+ 格式容错(M4) | Task 8 |
| 文档同步 + 全量验证 + PR | Task 9 |

**不在 PR2 范围**(后续 plan):
- PR3 文档专项(M5 陈旧计数 docstring ×8、§2.2 跨节一致、用户手册双向链接)
- 备忘录到点提醒(P1 提醒通道)
- priority / recurrence 字段(DB schema 改动,需独立 spec)

## Placeholder Scan(自检)

- ✅ 无 "TBD" / "TODO" / "fill in later"
- ✅ 无 "类似 Task N" 跨引用 —— 每个 task 内容完整独立(定位 helper、extractor 代码全量给出)
- ✅ 无 "Add appropriate error handling" 空话 —— 所有 `_dry_run`/`_confirmed` 含显式 user 守卫、DB try/except、found=False 返回
- ✅ 类型/签名一致:
  - `extract_update_params(query, today_str=None) -> UpdateParams | None`
  - `extract_delete_params(query, today_str=None) -> DeleteParams | None`
  - `MemoUpdateTool().execute(query, context=...) -> dict` / `MemoDeleteTool` 同
  - `_find_candidates(user, target_title)` 模块级(update/delete 共用)
- ✅ 计数断言同步设计(20→21→22)避免 PR1 T5 回归重演

## 与项目规则的兼容性

- 遵循 Plan-First(feature-development.md):本文档即 PR2 计划,用户批准后执行
- 遵循 feature-branch-workflow:`feat/memo-update-delete-tool` 分支 + PR + CI + 人工 merge
- 遵循 branch-and-release-strategy:feature → main(squash merge);不在此 PR bump VERSION/CHANGELOG(release 阶段统一 generate_release)
- 遵循 Python 环境规范:所有测试/ruff/mypy 用 `conda run -n OmniDesk`

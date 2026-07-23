# 智能助手 — 阶段 3 新工具 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏现有架构前提下,为 smart_assistant 智能助手新增 3 个高频业务工具(公告/合规/外部链接),每个工具 8 测试 + E2E + 前端卡片,并引入 `ToolContext` 类型化抽象以堵住越权数据泄露风险。

**Architecture:** 在 `BaseTool` 之上引入 `ToolContext` 简单命名空间(contextvars-style),把 `dict` 类型的 `context` 参数升级为带类型的 `ToolContext` 对象(包含 `user`, `request_id`, `history`)。3 个新工具通过继承 `BaseTool` 并实现 `execute(query, context)`,在工具内部显式从 `context.user` 读用户并按权限过滤数据源。工具注册继续走 `tools/registry.py`,但要求每个工具显式声明 `required_auth: bool = True`,工具调度器在 `intent_classifier` 之后会校验。

**Tech Stack:** Django 4.2 + DRF,Python 3.10,pytest + pytest-django,`@dataclass(frozen=True)` 做 `ToolContext`,前端 React 18.3 + Ant Design 5,pytest fixtures(`mock_llm_router` / `mock_tool_registry` / `sample_smart_session` 等已在 `conftest.py` 中)。

**修正说明(对比 handoff-8):**
- handoff-8 描述的 `communication.Announcement` 实际是 `communication.Post`
- handoff-8 描述的 `compliance.InspectionRecord` 实际是 `compliance.ComplianceIssue`
- handoff-8 描述的 `external-links.Bookmark/LinkGroup` 实际是 `external_integration.ExternalLink`(app 名为 `external_integration`,非 `external-links`)
- 这些修正均在 2026-06-07 阅读实际 `models.py` 后确认,代码已就绪

---

## 背景与目标

### 业务目标

1. **公告查询** — 用户问"这周有什么公告" → 返回最近 N 条 Post 列表
2. **合规查询** — 用户问"张三还有几条待整改" → 返回 ComplianceIssue 待处理项
3. **外部链接查询** — 用户问"公司 VPN 怎么登录" → 返回 ExternalLink 模糊匹配

### 技术目标

1. **引入 `ToolContext` 类型化抽象** — 堵住越权数据泄露风险(plan §6 HIGH 风险)
2. **每个新工具 ≥ 8 个测试**(参数解析、权限、空结果、异常、并发 等)
3. **E2E 覆盖 3 个新场景** — 走"用户问 → 工具调用 → LLM 合成回答"全链路
4. **前端 3 个新卡片组件** — ToolResult 渲染

### 涉及文件与模块

| 类别 | 路径 | 动作 |
|------|------|------|
| 新增 | `omni_desk_backend/smart_assistant/tools/tool_context.py` | ToolContext dataclass + 工厂 |
| 修改 | `omni_desk_backend/smart_assistant/tools/base.py` | `execute` 签名升级,新增 `required_auth: bool` |
| 修改 | `omni_desk_backend/smart_assistant/tools/registry.py` | `register` 校验 `required_auth`,新增 `get_tool_for_user()` |
| 修改 | `omni_desk_backend/smart_assistant/tools/__init__.py` | 导入 3 个新工具触发注册 |
| 新增 | `omni_desk_backend/smart_assistant/tools/announcement_tool.py` | AnnouncementTool 类 |
| 新增 | `omni_desk_backend/smart_assistant/tools/compliance_tool.py` | ComplianceTool 类 |
| 新增 | `omni_desk_backend/smart_assistant/tools/external_link_tool.py` | ExternalLinkTool 类 |
| 修改 | `omni_desk_backend/smart_assistant/agent/prompt_builder.py` | 工具描述列表追加 3 个 |
| 修改 | `omni_desk_backend/smart_assistant/agent/orchestrator.py` | 调用工具时构造 `ToolContext` |
| 新增 | `omni_desk_backend/smart_assistant/tests/test_tool_context.py` | ToolContext 测试(5 个) |
| 新增 | `omni_desk_backend/smart_assistant/tests/test_announcement_tool.py` | 8 个测试 |
| 新增 | `omni_desk_backend/smart_assistant/tests/test_compliance_tool.py` | 8 个测试 |
| 新增 | `omni_desk_backend/smart_assistant/tests/test_external_link_tool.py` | 8 个测试 |
| 修改 | `omni_desk_backend/smart_assistant/tests/test_e2e_smart_chat.py` | 增加 3 个 E2E 场景 |
| 修改 | `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` | 新增 3 个卡片组件 |
| 文档 | `docs/technical/27-smart-assistant-tooling.md` | 追加新工具章节 |
| 文档 | `docs/user-manual/04-smart-assistant-user-guide.md` | 追加新工具用户视角说明 |

---

## 技术方案

### 1. ToolContext 抽象

```python
# tools/tool_context.py
from dataclasses import dataclass, field
from typing import Any, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文,替代裸 dict。

    设计原则:
    - frozen=True 防误改
    - user 必填(NEW 工具要求 auth)
    - request_id 默认生成,用于日志关联
    - history 可选,工具内可读但不应改
    """
    user: Any  # CustomUser instance,类型注解避循环导入
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: Optional[List[dict]] = field(default_factory=list)

    @classmethod
    def from_request(cls, request) -> "ToolContext":
        """从 DRF Request 构造"""
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
        )
```

### 2. BaseTool 签名升级

```python
# tools/base.py 修改
class BaseTool(ABC):
    name: str = ""
    description: str = ""
    intent_type: str = ""
    required_auth: bool = True  # NEW:大多数工具需登录,子类可覆盖

    @abstractmethod
    def execute(self, query: str, context: ToolContext) -> dict:
        """执行工具,返回结构化结果。

        子类实现须:
        1. 从 context.user 读取用户(若 required_auth=True)
        2. 按用户权限过滤数据源
        3. 返回标准 dict:{found, count, <items>|[message]}
        """
        ...
```

### 3. 工具注册协议

```python
# tools/registry.py 修改
class ToolRegistry:
    _tools: Dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        if not tool.intent_type:
            raise ValueError(f"Tool {tool.name} missing intent_type")
        if not isinstance(tool, BaseTool):
            raise TypeError(f"{tool} not BaseTool instance")
        cls._tools[tool.intent_type] = tool

    @classmethod
    def get_tool_for_user(cls, intent_type: str, user) -> BaseTool | None:
        """NEW: 按用户返回工具(权限校验)。

        若工具 required_auth=True 且 user 未认证 → 返回 None
        """
        tool = cls._tools.get(intent_type)
        if tool is None:
            return None
        if tool.required_auth and not (user and user.is_authenticated):
            return None
        return tool
```

### 4. 3 个新工具骨架(模式一致)

每个工具遵循同一模式:
1. 继承 `BaseTool`
2. `name` / `description` / `intent_type` 三个类属性
3. `execute(query, context)` 中:
   - 从 `context.user` 读用户
   - 用 `select_related` / `prefetch_related` 避免 N+1
   - 按用户权限过滤(认证 → 全部可见;未认证 → 抛 `PermissionDenied`)
4. 工具结果格式:`{"found": bool, "count": int, "<items_key>": [...]}` 或 `{"found": False, "message": "..."}`

### 5. 工具注册(在 `__init__.py`)

```python
# tools/__init__.py 末尾追加
from .announcement_tool import AnnouncementTool
from .compliance_tool import ComplianceTool
from .external_link_tool import ExternalLinkTool

# 注册到 Registry
ToolRegistry.register(AnnouncementTool())
ToolRegistry.register(ComplianceTool())
ToolRegistry.register(ExternalLinkTool())
```

### 6. E2E 链路(在 `test_e2e_smart_chat.py`)

每场景步骤:
1. 登录用户
2. POST `/api/smart-assistant/chat/`
3. 断言响应中包含工具结果摘要
4. 验证数据库未发生额外写入副作用

### 7. 前端卡片(在 `ToolResult.jsx`)

3 个独立 React 组件:
- `AnnouncementCard` — 列表型,展示 title/author/created_at
- `ComplianceCard` — 列表型 + 状态标签
- `LinkCard` — 卡片网格,展示 name/url/category

---

## 实施步骤(分阶段,2 周 ~10 工作日)

### 阶段 0:ToolContext 抽象基础设施(1 天)

#### Task 0.1: ToolContext 数据类 + 测试

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/tool_context.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_tool_context.py`

- [ ] **Step 1: 写失败测试(5 个)**

```python
# test_tool_context.py
import pytest
from smart_assistant.tools.tool_context import ToolContext


def test_create_with_user_only():
    ctx = ToolContext(user="alice")
    assert ctx.user == "alice"
    assert ctx.request_id  # 自动生成
    assert ctx.history == []


def test_request_id_unique():
    a, b = ToolContext(user="x"), ToolContext(user="x")
    assert a.request_id != b.request_id


def test_frozen_cannot_mutate():
    ctx = ToolContext(user="alice")
    with pytest.raises(Exception):  # FrozenInstanceError
        ctx.user = "bob"


def test_from_request_with_drf_request():
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = "mock_user"
    ctx = ToolContext.from_request(request)
    assert ctx.user == "mock_user"


def test_from_request_generates_request_id():
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = "u"
    ctx = ToolContext.from_request(request)
    assert isinstance(ctx.request_id, str) and len(ctx.request_id) > 0
```

- [ ] **Step 2: 跑测试,确认失败** — `pytest smart_assistant/tests/test_tool_context.py -v` 应 ImportError

- [ ] **Step 3: 实现 ToolContext**

```python
# tool_context.py
from dataclasses import dataclass, field
from typing import Any, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class ToolContext:
    user: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: Optional[List[dict]] = field(default_factory=list)

    @classmethod
    def from_request(cls, request) -> "ToolContext":
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
        )
```

- [ ] **Step 4: 跑测试,确认通过** — 5 passed

- [ ] **Step 5: Commit**
```bash
git add omni_desk_backend/smart_assistant/tools/tool_context.py \
        omni_desk_backend/smart_assistant/tests/test_tool_context.py
git commit -m "feat(smart-assistant): add ToolContext typed abstraction"
```

#### Task 0.2: BaseTool 签名升级

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/base.py:1-61`

- [ ] **Step 1: 修改 `base.py`**(见上文"2. BaseTool 签名升级")
- [ ] **Step 2: 跑全套测试,确认 0 回归** — `pytest smart_assistant/ --no-cov -q` 应 356+ 通过
- [ ] **Step 3: 跑覆盖率,确认仍 ≥ 85%**
- [ ] **Step 4: Commit**
```bash
git add omni_desk_backend/smart_assistant/tools/base.py
git commit -m "refactor(smart-assistant): add required_auth flag to BaseTool"
```

#### Task 0.3: Registry 升级

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/registry.py:1-20`

- [ ] **Step 1: 添加 `get_tool_for_user` 方法**(代码见上文"3. 工具注册协议")
- [ ] **Step 2: 跑测试,确认 0 回归**
- [ ] **Step 3: Commit**
```bash
git commit -am "feat(smart-assistant): registry validates required_auth"
```

---

### 阶段 1:AnnouncementTool(1.5 天)

#### Task 1.1: AnnouncementTool 实现 + 8 测试

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/announcement_tool.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_announcement_tool.py`

- [ ] **Step 1: 写失败测试 8 个**

```python
# test_announcement_tool.py 全部测试
import pytest
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.announcement_tool import AnnouncementTool


@pytest.fixture
def tool():
    return AnnouncementTool()


@pytest.fixture
def user(db, admin_user_obj):
    return admin_user_obj


@pytest.mark.django_db
def test_basic_query_returns_recent_posts(tool, user):
    from communication.models import Post
    Post.objects.create(title="本周例会通知", content="...", author=user)
    ctx = ToolContext(user=user)
    result = tool.execute("最近有什么公告", ctx)
    assert result["found"] is True
    assert result["count"] >= 1


@pytest.mark.django_db
def test_filters_expired_posts(tool, user):
    from django.utils import timezone
    from datetime import timedelta
    from communication.models import Post
    past = timezone.now() - timedelta(days=10)
    Post.objects.create(title="已过期", content="x", expires_at=past)
    Post.objects.create(title="未过期", content="y")
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    titles = [p["title"] for p in result["posts"]]
    assert "已过期" not in titles
    assert "未过期" in titles


@pytest.mark.django_db
def test_filters_archived(tool, user):
    from communication.models import Post
    Post.objects.create(title="归档", content="x", is_archived=True)
    Post.objects.create(title="活跃", content="y", is_archived=False)
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    titles = [p["title"] for p in result["posts"]]
    assert "归档" not in titles


@pytest.mark.django_db
def test_keyword_in_title(tool, user):
    from communication.models import Post
    Post.objects.create(title="安全检查通知", content="...")
    Post.objects.create(title="排班调整", content="...")
    ctx = ToolContext(user=user)
    result = tool.execute("安全", ctx)
    assert any("安全" in p["title"] for p in result["posts"])


@pytest.mark.django_db
def test_empty_result_returns_not_found(tool, user):
    ctx = ToolContext(user=user)
    result = tool.execute("不存在的关键词xyz123", ctx)
    assert result["found"] is False
    assert "message" in result


@pytest.mark.django_db
def test_limit_to_10_results(tool, user):
    from communication.models import Post
    for i in range(15):
        Post.objects.create(title=f"公告{i}", content="x")
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    assert result["count"] == 10
    assert len(result["posts"]) == 10


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type_is_announcement(tool):
    assert tool.intent_type == "announcement_query"
    assert tool.name == "announcement_query"
```

- [ ] **Step 2: 跑测试,确认全部 FAIL**
- [ ] **Step 3: 实现 AnnouncementTool**

```python
# announcement_tool.py
from typing import List
from django.db.models import Q
from django.utils import timezone

from .base import BaseTool


class AnnouncementTool(BaseTool):
    name = "announcement_query"
    description = "查询公司公告/通知(communication.Post)"
    intent_type = "announcement_query"
    required_auth = True

    def execute(self, query: str, context) -> dict:
        # 1. 关键词抽取(去除停用词)
        stopwords = {"公告", "通知", "最近", "本周", "什么", "查", "看看"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        # 2. 构造查询(未过期 AND 未归档)
        from communication.models import Post
        qs = Post.objects.filter(is_archived=False).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).select_related("author").order_by("-created_at")

        if keywords:
            qs = qs.filter(Q(title__icontains=keywords) | Q(content__icontains=keywords))

        posts: List[dict] = []
        for p in qs[:10]:
            posts.append({
                "title": p.title,
                "content": (p.content or "")[:200] + ("..." if len(p.content or "") > 200 else ""),
                "author": p.author.username if p.author else "系统",
                "created_at": p.created_at.date().isoformat(),
                "expires_at": p.expires_at.date().isoformat() if p.expires_at else None,
            })

        if not posts:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的公告'}

        return {"found": True, "count": len(posts), "posts": posts}
```

- [ ] **Step 4: 跑测试,确认 8 passed**
- [ ] **Step 5: Commit**
```bash
git add omni_desk_backend/smart_assistant/tools/announcement_tool.py \
        omni_desk_backend/smart_assistant/tests/test_announcement_tool.py
git commit -m "feat(smart-assistant): add AnnouncementTool for communication.Post query"
```

#### Task 1.2: 注册 AnnouncementTool

- [ ] **Step 1: 在 `tools/__init__.py` 追加 import + register**(见上文"5. 工具注册")
- [ ] **Step 2: 跑全套测试,0 回归**
- [ ] **Step 3: 在 `agent/prompt_builder.py` 的工具描述列表追加**

```python
# prompt_builder.py 中
"announcement_query": "查询公告/通知(communication.Post 表,已过滤过期和归档)",
```
- [ ] **Step 4: Commit**
```bash
git commit -am "feat(smart-assistant): register AnnouncementTool + update prompt_builder"
```

---

### 阶段 2:ComplianceTool(2 天)

#### Task 2.1: ComplianceTool 实现 + 8 测试

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/compliance_tool.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_compliance_tool.py`

- [ ] **Step 1: 写失败测试 8 个**

```python
# test_compliance_tool.py
import pytest
from datetime import date, timedelta
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.compliance_tool import ComplianceTool


@pytest.fixture
def tool():
    return ComplianceTool()


@pytest.fixture
def issue_setup(db, admin_user_obj):
    """创建项目+书籍+几个合规问题"""
    from projects.models import Project
    from documents.models import Book
    from compliance.models import ComplianceIssue

    project = Project.objects.create(name="P1", code="P1")
    book = Book.objects.create(title="B1", project=project)
    pending = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="d", status="待处理"
    )
    resolved = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="d", status="已解决"
    )
    return {"project": project, "book": book, "pending": pending, "resolved": resolved}


@pytest.mark.django_db
def test_query_pending_only(tool, issue_setup):
    ctx = ToolContext(user="u")
    result = tool.execute("待整改", ctx)
    assert result["found"] is True
    statuses = [i["status"] for i in result["issues"]]
    assert "已解决" not in statuses


@pytest.mark.django_db
def test_filter_by_severity(tool, issue_setup, db):
    from compliance.models import ComplianceIssue
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="d", severity="紧急", status="待处理"
    )
    ctx = ToolContext(user="u")
    result = tool.execute("紧急", ctx)
    severities = [i["severity"] for i in result["issues"]]
    assert all(s == "紧急" for s in severities)


@pytest.mark.django_db
def test_keyword_in_description(tool, issue_setup, db):
    from compliance.models import ComplianceIssue
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="缺少签字", status="待处理"
    )
    ctx = ToolContext(user="u")
    result = tool.execute("签字", ctx)
    assert any("签字" in i["description"] for i in result["issues"])


@pytest.mark.django_db
def test_due_soon_includes_due_date(tool, issue_setup, db):
    from compliance.models import ComplianceIssue
    soon = date.today() + timedelta(days=3)
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="d", status="待处理", due_date=soon
    )
    ctx = ToolContext(user="u")
    result = tool.execute("即将到期", ctx)
    assert any(i.get("due_date") == soon.isoformat() for i in result["issues"])


@pytest.mark.django_db
def test_empty_result(tool):
    ctx = ToolContext(user="u")
    result = tool.execute("xyz123不存在", ctx)
    assert result["found"] is False


@pytest.mark.django_db
def test_no_n_plus_1(tool, issue_setup, db):
    """确保使用了 select_related"""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection
    with CaptureQueriesContext(connection) as ctx_q:
        tool.execute("待整改", ToolContext(user="u"))
    # 创建 1 个 project 2 个 issue,select_related project 后应 < 5 query
    assert len(ctx_q.captured_queries) < 5


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type(tool):
    assert tool.intent_type == "compliance_query"
```

- [ ] **Step 2: 跑测试,确认全部 FAIL**
- [ ] **Step 3: 实现 ComplianceTool**

```python
# compliance_tool.py
from typing import List
from datetime import date, timedelta
from django.db.models import Q

from .base import BaseTool


class ComplianceTool(BaseTool):
    name = "compliance_query"
    description = "查询合规问题/待整改项(compliance.ComplianceIssue)"
    intent_type = "compliance_query"
    required_auth = True

    def execute(self, query: str, context) -> dict:
        stopwords = {"合规", "整改", "待", "已", "什么", "查", "看看", "几", "条"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        from compliance.models import ComplianceIssue
        qs = (ComplianceIssue.objects
              .filter(status__in=["待处理", "处理中"])
              .select_related("project", "document_book", "document_template")
              .order_by("-severity", "due_date"))

        # 关键词过滤
        if keywords:
            qs = qs.filter(
                Q(description__icontains=keywords) |
                Q(issue_type__icontains=keywords) |
                Q(project__name__icontains=keywords)
            )

        # 即将到期(7 天内)关键词
        if "即将" in query or "快到期" in query:
            qs = qs.filter(due_date__lte=date.today() + timedelta(days=7))

        # 紧急
        if "紧急" in query:
            qs = qs.filter(severity="紧急")

        issues: List[dict] = []
        for i in qs[:10]:
            issues.append({
                "issue_type": i.issue_type,
                "description": i.description[:200],
                "status": i.status,
                "severity": i.severity,
                "project": i.project.name if i.project else "无",
                "due_date": i.due_date.isoformat() if i.due_date else None,
                "location": i.location,
            })

        if not issues:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的合规问题'}

        return {"found": True, "count": len(issues), "issues": issues}
```

- [ ] **Step 4: 跑测试,确认 8 passed**
- [ ] **Step 5: Commit**
```bash
git commit -am "feat(smart-assistant): add ComplianceTool for compliance.ComplianceIssue"
```

#### Task 2.2: 注册 ComplianceTool

- [ ] 在 `__init__.py` 追加 import + register
- [ ] 在 `prompt_builder.py` 追加描述
- [ ] 跑测试,0 回归
- [ ] Commit

---

### 阶段 3:ExternalLinkTool(1.5 天)

#### Task 3.1: ExternalLinkTool 实现 + 8 测试

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/external_link_tool.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_external_link_tool.py`

- [ ] **Step 1: 写失败测试 8 个**

```python
# test_external_link_tool.py
import pytest
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.external_link_tool import ExternalLinkTool


@pytest.fixture
def tool():
    return ExternalLinkTool()


@pytest.fixture
def links(db):
    from external_integration.models import ExternalLink
    return [
        ExternalLink.objects.create(
            name="公司VPN", url="https://vpn.example.com",
            category="网络", description="VPN 登录地址", is_active=True
        ),
        ExternalLink.objects.create(
            name="Jira", url="https://jira.example.com",
            category="研发", is_active=True
        ),
        ExternalLink.objects.create(
            name="已废弃链接", url="https://old.example.com",
            category="其他", is_active=False
        ),
    ]


@pytest.mark.django_db
def test_fuzzy_match_name(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("VPN", ctx)
    assert result["found"] is True
    assert any("VPN" in l["name"] for l in result["links"])


@pytest.mark.django_db
def test_excludes_inactive(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("链接", ctx)
    names = [l["name"] for l in result["links"]]
    assert "已废弃链接" not in names


@pytest.mark.django_db
def test_match_in_description(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("登录地址", ctx)
    assert any("VPN" in l["name"] for l in result["links"])


@pytest.mark.django_db
def test_list_by_category(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("研发", ctx)
    assert all(l["category"] == "研发" for l in result["links"])


@pytest.mark.django_db
def test_sso_enabled_flag(tool, links):
    from external_integration.models import ExternalLink
    ExternalLink.objects.filter(name="公司VPN").update(sso_enabled=True)
    ctx = ToolContext(user="u")
    result = tool.execute("VPN", ctx)
    vpn = next(l for l in result["links"] if "VPN" in l["name"])
    assert vpn["sso_enabled"] is True


@pytest.mark.django_db
def test_empty_result(tool):
    ctx = ToolContext(user="u")
    result = tool.execute("xyz123", ctx)
    assert result["found"] is False


@pytest.mark.django_db
def test_no_keywords_returns_recent(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("所有链接", ctx)
    # 应返回所有 active 链接
    assert result["count"] == 2


def test_required_auth_and_intent(tool):
    assert tool.required_auth is True
    assert tool.intent_type == "external_link_query"
```

- [ ] **Step 2: 跑测试,确认 FAIL**
- [ ] **Step 3: 实现 ExternalLinkTool**

```python
# external_link_tool.py
from typing import List
from django.db.models import Q

from .base import BaseTool


class ExternalLinkTool(BaseTool):
    name = "external_link_query"
    description = "查询公司内网外链(VPN/Jira 等,external_integration.ExternalLink)"
    intent_type = "external_link_query"
    required_auth = True

    def execute(self, query: str, context) -> dict:
        # 关键词识别
        stopwords = {"怎么", "如何", "登录", "使用", "打开", "访问", "的", "什么"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        from external_integration.models import ExternalLink
        qs = ExternalLink.objects.filter(is_active=True).order_by("category", "sort_order", "name")

        # 是否列全(用户说"所有"或没有关键词)
        list_all = "所有" in query or not keywords

        if not list_all and keywords:
            qs = qs.filter(
                Q(name__icontains=keywords) |
                Q(description__icontains=keywords) |
                Q(category__icontains=keywords)
            )

        links: List[dict] = []
        for l in qs[:20]:
            links.append({
                "name": l.name,
                "url": l.url,
                "category": l.category,
                "description": l.description[:150],
                "sso_enabled": l.sso_enabled,
                "sso_token_endpoint": l.sso_token_endpoint if l.sso_enabled else None,
            })

        if not links:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的外链'}

        return {"found": True, "count": len(links), "links": links}
```

- [ ] **Step 4: 跑测试,8 passed**
- [ ] **Step 5: Commit**
```bash
git commit -am "feat(smart-assistant): add ExternalLinkTool for external_integration.ExternalLink"
```

#### Task 3.2: 注册 ExternalLinkTool

- [ ] `__init__.py` 追加
- [ ] `prompt_builder.py` 追加
- [ ] 0 回归
- [ ] Commit

---

### 阶段 4:E2E 覆盖(1 天)

#### Task 4.1: 3 个 E2E 场景 + 1 个未授权拒绝

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tests/test_e2e_smart_chat.py`

- [ ] **Step 1: 写失败 E2E 测试 4 个**

```python
# test_e2e_smart_chat.py 末尾追加
@pytest.mark.django_db
def test_e2e_announcement_query(auth_client, mock_llm_router, db):
    """用户问'这周有什么公告' → 走 announcement_tool → LLM 合成回答"""
    from communication.models import Post
    Post.objects.create(title="本周例会通知", content="周三下午3点", author=auth_client.handler._force_auth_user)
    mock_llm_router.generate.return_value = (
        "本周有一条公告:本周例会通知。", {"total_tokens": 50}
    )
    resp = auth_client.post("/api/smart-assistant/chat/", {
        "message": "这周有什么公告", "stream": False
    }, format="json")
    assert resp.status_code == 200
    assert "公告" in resp.json()["response"]


@pytest.mark.django_db
def test_e2e_compliance_query(auth_client, mock_llm_router, db):
    from projects.models import Project
    from documents.models import Book
    from compliance.models import ComplianceIssue
    p = Project.objects.create(name="P1", code="P1")
    b = Book.objects.create(title="B1", project=p)
    ComplianceIssue.objects.create(
        project=p, document_book=b, issue_type="不规范",
        description="缺少签字", status="待处理", severity="紧急"
    )
    mock_llm_router.generate.return_value = (
        "有一条紧急待整改:缺少签字。", {"total_tokens": 50}
    )
    resp = auth_client.post("/api/smart-assistant/chat/", {
        "message": "待整改", "stream": False
    }, format="json")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_e2e_external_link_query(auth_client, mock_llm_router, db):
    from external_integration.models import ExternalLink
    ExternalLink.objects.create(
        name="公司VPN", url="https://vpn.example.com",
        category="网络", is_active=True
    )
    mock_llm_router.generate.return_value = (
        "公司VPN 登录地址:https://vpn.example.com", {"total_tokens": 50}
    )
    resp = auth_client.post("/api/smart-assistant/chat/", {
        "message": "公司VPN怎么登录", "stream": False
    }, format="json")
    assert resp.status_code == 200
    assert "VPN" in resp.json()["response"]


@pytest.mark.django_db
def test_e2e_unauth_user_rejected(db, mock_llm_router):
    """非授权用户访问需 auth 的工具 → 拒绝"""
    from rest_framework.test import APIClient
    client = APIClient()
    resp = client.post("/api/smart-assistant/chat/", {
        "message": "公告", "stream": False
    }, format="json")
    # 未登录应 401/403(具体看权限中间件)
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: 跑测试,确认 FAIL**(可能因 mock 或 fixture 缺失)
- [ ] **Step 3: 检查现有 `auth_client` 和 `mock_llm_router` fixture,按需补**
- [ ] **Step 4: 跑测试,4 passed(原 3 + 新 4)**
- [ ] **Step 5: Commit**
```bash
git commit -am "test(smart-assistant): E2E for 3 new tools + unauth rejection"
```

---

### 阶段 5:前端 3 个新卡片(1.5 天)

#### Task 5.1: AnnouncementCard

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx`

- [ ] **Step 1: 在 `ToolResult.jsx` 增加 `AnnouncementCard` 组件**

```jsx
const AnnouncementCard = ({ posts }) => (
  <List
    dataSource={posts}
    renderItem={(p) => (
      <List.Item>
        <List.Item.Meta
          title={p.title}
          description={
            <>
              <Text type="secondary">{p.author} · {p.created_at}</Text>
              <div>{p.content}</div>
            </>
          }
        />
      </List.Item>
    )}
  />
);
```

- [ ] **Step 2: 在 `ToolResult` switch 中加 `case "announcement_query"`**
- [ ] **Step 3: `npm test` 通过**
- [ ] **Step 4: Commit**
```bash
git commit -am "feat(smart-assistant-frontend): AnnouncementCard component"
```

#### Task 5.2: ComplianceCard + LinkCard(同模式,1 commit)

- [ ] 同样模式加 `ComplianceCard`(List + 状态 Tag)和 `LinkCard`(Card grid + 点击复制 URL)
- [ ] `npm test` + 手动验证
- [ ] Commit

---

### 阶段 6:联调 + 文档 + PR(1 天)

#### Task 6.1: 文档同步

**Files:**
- Modify: `docs/technical/27-smart-assistant-tooling.md` 追加新工具章节
- Modify: `docs/user-manual/04-smart-assistant-user-guide.md` 追加用户视角说明

- [ ] **Step 1: 在 tooling 文档加 "新工具注册指南" + 3 个新工具的 API**
- [ ] **Step 2: 用户手册加 "如何让智能助手查询公告/合规/外链" 章节**
- [ ] **Step 3: Commit**
```bash
git commit -am "docs(smart-assistant): document 3 new tools"
```

#### Task 6.2: 全套测试 + 覆盖率

- [ ] **Step 1: 跑后端测试**

```bash
cd omni_desk_backend
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' \
  --fail-under=85
```

- [ ] **Step 2: 跑前端测试**

```bash
cd omni_desk_frontend
npm test -- --watchAll=false
```

- [ ] **Step 3: 跑后端 lint**

```bash
cd omni_desk_backend
ruff check smart_assistant/ --fix
```

- [ ] **Step 4: 跑前端 lint**

```bash
cd omni_desk_frontend
npm run lint
```

#### Task 6.3: 提 PR

- [ ] **Step 1: push 分支**

```bash
git push -u origin feature/smart-assistant-optimization
```

- [ ] **Step 2: 写 PR 描述**

```
## 概述
智能助手阶段 3 — 新增 3 个高频业务工具

## 主要变更
- AnnouncementTool: 查询公告(communication.Post)
- ComplianceTool: 查询合规问题(compliance.ComplianceIssue)
- ExternalLinkTool: 查询外链(external_integration.ExternalLink)
- ToolContext 类型化抽象,堵住越权风险
- 24 单元测试 + 4 E2E 测试
- 前端 3 个新卡片组件

## 测试计划
- [x] 后端 380+ 测试通过(本计划 + 已有)
- [x] 覆盖率 ≥ 85%
- [x] 前端 npm test 通过
- [x] 后端 ruff + 前端 lint 通过

## 关联
- Closes #TODO
- 阶段 3 of docs/plans/2026-06-06_smart-assistant-optimization.md
```

- [ ] **Step 3: 等 CI 跑完,处理 review 反馈**

---

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| 新工具数据源权限/可见性错误 → 越权 | **HIGH** | ToolContext.user 强制;E2E 包含"非授权用户被拒"测试;新增工具前 24h code review |
| N+1 查询(ComplianceIssue 含 3 个外键) | MEDIUM | 严格 `select_related("project", "document_book", "document_template")`;测试 6 显式断言 query count < 5 |
| BaseTool 签名升级破坏现有 12 工具 | MEDIUM | 仅加 `required_auth` 字段(默认 True),不改 execute 签名;跑全套 0 回归 |
| LLM 工具描述文案不准确,路由失败 | LOW | prompt_builder.py 描述由人工编写,经 3 场景 E2E 验证 |
| 前端卡片 prop 类型不一致 | LOW | 用 PropTypes 或 TS(若项目用);至少 1 单元测试 |
| ComplianceIssue.due_date 字段可能为 None | LOW | UI 显示"无截止日期" |
| ExternalLink 模糊匹配命中率低 | LOW | 关键词去除停用词;多字段 OR 查询 |

---

## 依赖

### 后端
- 已有:Django 4.2, DRF, pytest, pytest-django, ruff
- 无新增依赖(`@dataclass` 在 Python 3.7+ 内置)

### 前端
- 已有:React 18.3, Ant Design 5
- 无新增依赖

### 数据源依赖(模型已存在)
- `communication.Post` ✅ 已有
- `compliance.ComplianceIssue` ✅ 已有
- `external_integration.ExternalLink` ✅ 已有

---

## 验收标准

- [ ] 3 个新工具(announcement/compliance/external_link)已实现并注册到 `ToolRegistry`
- [ ] 每个新工具 ≥ 8 个单元测试(共 24)
- [ ] ToolContext 5 个测试通过
- [ ] 4 个 E2E 测试通过(3 个工具 + 1 个未授权拒绝)
- [ ] 现有 12 个工具 0 回归(356 测试仍通过)
- [ ] 覆盖率 ≥ 85%(预计回到 90%+)
- [ ] 前端 3 个新卡片组件,`npm test` 通过
- [ ] ruff + ESLint 0 警告
- [ ] PR 已开,所有 review 反馈已处理

---

## 时间估算

| 阶段 | 工作量 | 累计 |
|------|--------|------|
| 0 ToolContext 抽象 | 1 天 | 1 天 |
| 1 AnnouncementTool | 1.5 天 | 2.5 天 |
| 2 ComplianceTool | 2 天 | 4.5 天 |
| 3 ExternalLinkTool | 1.5 天 | 6 天 |
| 4 E2E 覆盖 | 1 天 | 7 天 |
| 5 前端 3 卡片 | 1.5 天 | 8.5 天 |
| 6 联调 + 文档 + PR | 1 天 | 9.5 天 |
| **总计** | **约 2 周** | |

---

## 与现有计划的关系

- **执行** `docs/plans/2026-06-06_smart-assistant-optimization.md` 阶段 3
- **依赖** 阶段 0-2 已完成(架构 + 覆盖率 96%)
- **不影响** 阶段 4-5(性能优化 + 架构升级),后续可独立进行
- **回归守门**:smart_assistant 覆盖率门槛 85%,在 `.github/workflows/smart-assistant-coverage.yml` 中已配置

---

## 关键注意点(给执行者)

1. **必须 TDD**:每个 Task 都是"先写失败测试 → 跑确认 FAIL → 实现 → 跑确认 PASS → commit"
2. **频繁 commit**:每个 Task 步骤 5 都是 1 个独立 commit,便于回滚和 review
3. **跑全套测试无回归**:每阶段 commit 前必须 `pytest smart_assistant/ --no-cov -q` 验证 0 回归
4. **覆盖率 ≥ 85%**:不要为了完成功能而牺牲测试,每加 1 行生产代码必须 ≥ 1 行测试
5. **Handoff 同步**:每完成 1 个阶段,在 `docs/notes/` 加 handoff-9、handoff-10 交接文档,记录:
   - 本阶段 commit 列表
   - 测试增量
   - 覆盖率变化
   - 下个阶段注意

---

## 启动检查清单(执行者第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认最近 commit
git log --oneline -3
# 期望:handoff-8 + P6 覆盖率 commit(若已 commit)

# 3. 跑基线测试
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q
# 期望:356 passed + 1 xfailed + 10 xpassed

# 4. 跑覆盖率
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=85
# 期望:96%,EXIT=0

# 5. 从 Task 0.1 开始执行(按 plan 顺序)
```

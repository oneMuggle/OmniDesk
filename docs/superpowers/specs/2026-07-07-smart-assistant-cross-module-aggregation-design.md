# 智能助手 — 跨模块汇总查询 设计规范

**日期:** 2026-07-07
**项目:** OmniDesk
**作者:** Claude
**状态:** 待用户审阅

---

## 1. 背景与目标

### 1.1 问题

OmniDesk 智能助手(`smart_assistant`)已接入 13 个业务工具(`ScheduleTool`/`AnnouncementTool`/`MeetingRoomTool` 等),但**当前是"单工具调用"模式**:

- 用户问"这周我有哪些事" → IntentClassifier 通常只路由到 1 个工具(如 `ScheduleTool`)
- LLM 拿到部分数据,综合回答质量差
- 工具无统一权限模型,全公司可见或本人可见一刀切

### 1.2 目标

让智能助手支持**跨模块汇总查询**:一次对话里同时调用多个工具,按分层权限过滤数据,综合呈现给用户。

### 1.3 范围(明确做与不做)

| 做 | 不做 |
|---|---|
| 按需多模块查询(LLM 自动编排多工具) | 写操作(代用户创建排班/预约会议室) |
| 分层权限(本人/部门/全量,助手自动判断) | 主动推送(每天早上推送今日安排) |
| 实时拉取(本阶段) | 预聚合 / 物化视图(后续再考虑) |
| 工具层 + ResultSynthesizer 升级 | Agent 主框架(IntentClassifier / ToolChainPlanner) |
| **全部 13 个工具实现 `_scope_self`**(否则启动失败) | 仅 3 个工具支持跨模块汇总 |
| **3 个核心工具(Schedule/MeetingRoom/Announcement)升级 `execute` 签名** | 其余 10 个工具沿用旧签名(向后兼容) |
| 75 个新测试 + 启动时 scope 校验 | Dify / RAGFlow 接入改造 |
| 前端 `AggregatedDayCard` 聚合卡片 | 个人仪表盘 widget(独立项目) |

**重要澄清:** `_scope_self` 实现范围 = 全部 13 个工具(防止遗漏);`execute` 签名升级范围 = 仅 3 个核心工具(其余人调用 `execute(query, ctx)` 旧路径,不进入跨模块汇总)。`BaseTool` 通过 isinstance 判定:`hasattr(self, 'build_base_queryset')` 走新路径,否则走旧路径。

---

## 2. 设计方案

### 2.1 架构

```
                    用户: "这周我有哪些事"
                              │
                              ▼
              ┌────────────────────────────┐
              │   IntentClassifier (已存在) │ ──→ needs_multi_tool=True
              └────────────────────────────┘
                              │
                              ▼
              ┌────────────────────────────┐
              │  ToolChainPlanner (已存在)  │ ──→ 多工具计划
              └────────────────────────────┘
                              │
                              ▼
              ┌────────────────────────────────────────────┐
              │ ToolChainExecutor (升级)                   │
              │   构造 ToolContext (含 scope)              │
              │   对每个工具:                              │
              │     base_qs = tool.build_base_queryset()   │
              │     scoped_qs = tool.get_queryset_for_scope│
              │                 (base_qs, context)         │
              │     result = tool.execute(params, scope,   │
              │                           qs)              │
              └────────────────────────────────────────────┘
                              │
                              ▼
              ┌────────────────────────────────────────────┐
              │ ResultSynthesizer (升级)                   │
              │   - 按时间线排序                            │
              │   - 同主题合并                              │
              │   - 输出结构化 JSON 给前端聚合卡片渲染    │
              └────────────────────────────────────────────┘
                              │
                              ▼
                          最终回答(Markdown + 卡片数据)
```

### 2.2 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| Agent 主框架 | **不动** | IntentClassifier / ToolChainPlanner / ConversationContext 已成熟 |
| 权限抽象点 | `BaseTool.get_queryset_for_scope()` 抽象方法 | 强制每个工具显式定义 3 种 scope,杜绝隐式越权 |
| 工具 `execute` 签名变化 | 从 `execute(query, ctx)` → `execute(params, scope, qs)` | qs 已过滤,工具只负责业务逻辑(关键词/排序/序列化) |
| 性能策略 | 实时 + 现有 3 级缓存 | 用户明确选择"先实时后续优化",YAGNI |
| 缓存失效 | 写时不清除,2 小时 TTL 自然过期 | 排班变更后用户最多看 2 小时旧数据,可接受 |
| 启动时校验 | `python manage.py check_tool_scopes` CI 跑 | 不让"未实现 `_scope_self`"的代码上生产 |

---

## 3. 组件设计

### 3.1 新增文件

| 路径 | 用途 |
|---|---|
| `omni_desk_backend/smart_assistant/scope.py` | `SmartAssistantScope` 枚举 + `resolve_scope()` 派生函数 |
| `omni_desk_backend/smart_assistant/agent/result_synthesizer.py` | `ResultSynthesizer` 类(多工具结果聚合/排序/合并) |
| `omni_desk_backend/smart_assistant/management/commands/check_tool_scopes.py` | 启动时校验所有工具实现 scope 方法 |
| `omni_desk_backend/smart_assistant/tests/test_scope.py` | scope 枚举 + resolve_scope 单元测试 |
| `omni_desk_backend/smart_assistant/tests/test_base_tool.py` | BaseTool 抽象方法测试 |
| `omni_desk_backend/smart_assistant/tests/test_result_synthesizer.py` | Synthesizer 单元测试 |
| `omni_desk_backend/smart_assistant/tests/test_tool_chain_executor.py` | Executor scope 注入 + 降级测试 |
| `omni_desk_backend/smart_assistant/tests/test_orchestrator_integration.py` | 端到端 scope 链路测试 |
| `omni_desk_backend/smart_assistant/tests/test_check_tool_scopes_cmd.py` | management command 测试 |
| `omni_desk_frontend/src/features/smart-assistant/components/AggregatedDayCard.jsx` | 跨模块聚合卡片组件 |
| `omni_desk_frontend/src/features/smart-assistant/components/__tests__/AggregatedDayCard.test.jsx` | 卡片组件测试 |

### 3.2 修改文件(最小改动)

| 路径 | 改动 |
|---|---|
| `omni_desk_backend/smart_assistant/tools/tool_context.py` | `ToolContext` 增加 `scope` 字段,`from_request` 自动调用 `resolve_scope` |
| `omni_desk_backend/smart_assistant/tools/base.py` | `BaseTool` 新增 `build_base_queryset()` 和 `get_queryset_for_scope()` 抽象方法,以及 `_scope_self()` 抽象方法 |
| `omni_desk_backend/smart_assistant/tools/__init__.py` | 无需改动(工具注册沿用 `tools/registry.py`,ResultSynthesizer 在 agent 层) |
| `omni_desk_backend/smart_assistant/tools/schedule_tool.py` | 实现 `_scope_self` / `_scope_department`;`execute` 接受 `qs` 参数 |
| `omni_desk_backend/smart_assistant/tools/meeting_room_tool.py` | 同上,会议室版本 |
| `omni_desk_backend/smart_assistant/tools/announcement_tool.py` | 同上,公告版本 |
| `omni_desk_backend/smart_assistant/agent/prompt_builder.py` | 工具描述列表追加"汇总场景"提示 |
| `omni_desk_backend/smart_assistant/agent/orchestrator.py` | 调用 `ResultSynthesizer` 替换原有单一返回路径 |
| `omni_desk_backend/smart_assistant/tools/registry.py` | 无改动(已支持 `get_tool_for_user`) |
| `omni_desk_backend/smart_assistant/apps.py` | `ready()` 钩子调用 `check_tool_scopes` 校验(仅 DEBUG=True) |
| `omni_desk_backend/smart_assistant/tests/conftest.py` | 新增 `scoped_user` / `dept_manager_user` / `global_user` fixture |
| `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` | 注册 `<AggregatedDayCard>` 组件 |

---

## 4. 关键组件接口

### 4.1 `SmartAssistantScope` 枚举

```python
# smart_assistant/scope.py
from enum import Enum

class SmartAssistantScope(Enum):
    SELF = "self"
    DEPARTMENT = "department"
    GLOBAL = "global"

def resolve_scope(user) -> SmartAssistantScope:
    """从用户身份派生权限范围(单一事实来源)"""
    if user.is_superuser or user.has_perm("smart_assistant.view_global"):
        return SmartAssistantScope.GLOBAL
    if user.has_perm("smart_assistant.view_department"):
        return SmartAssistantScope.DEPARTMENT
    return SmartAssistantScope.SELF
```

### 4.2 `ToolContext` 扩展

```python
# smart_assistant/tools/tool_context.py
@dataclass(frozen=True)
class ToolContext:
    user: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: Optional[List[dict]] = field(default_factory=list)
    scope: SmartAssistantScope = SmartAssistantScope.SELF  # ← 新增

    @classmethod
    def from_request(cls, request) -> "ToolContext":
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
            scope=resolve_scope(request.user),  # ← 自动派生
        )
```

### 4.3 `BaseTool` 新抽象方法

```python
class BaseTool(ABC):
    name: str = ""
    description: str = ""
    intent_type: str = ""
    required_auth: bool = True

    @abstractmethod
    def build_base_queryset(self):
        """返回未过滤的 QuerySet(子类必须实现)"""
        raise NotImplementedError

    @abstractmethod
    def get_queryset_for_scope(self, base_qs, context: ToolContext):
        """根据 scope 过滤 QuerySet(子类必须实现)"""
        if context.scope == SmartAssistantScope.SELF:
            return self._scope_self(base_qs, context)
        elif context.scope == SmartAssistantScope.DEPARTMENT:
            return self._scope_department(base_qs, context)
        return base_qs  # GLOBAL 不过滤

    @abstractmethod
    def _scope_self(self, qs, ctx):
        """本人范围过滤(子类必须实现)"""
        raise NotImplementedError

    def _scope_department(self, qs, ctx):
        """部门范围过滤(默认 = GLOBAL,子类可重写)"""
        return qs
```

### 4.4 `ResultSynthesizer` 接口

```python
class ResultSynthesizer:
    def synthesize(self, tool_results: List[dict], query: str) -> dict:
        """输入:多工具结果列表。输出:结构化聚合数据(前端卡片可直接消费)"""
        items = []
        for r in tool_results:
            for raw_item in r.get("items", []):  # 每条工具结果展开
                items.append({
                    "type": r["tool"],                # "schedule_query" / "meeting_room_query" / ...
                    "module": r["module_label"],      # "排班" / "会议" / "公告" (前端显示用)
                    "data": raw_item,                 # 原工具结果 dict
                    "sort_key": raw_item.get("start_at") or raw_item.get("created_at") or "9999",
                })
        items.sort(key=lambda x: x["sort_key"])

        module_counts = {}
        for it in items:
            module_counts[it["module"]] = module_counts.get(it["module"], 0) + 1

        summary_parts = [f"{m}{n}条" for m, n in module_counts.items()]
        summary = f"共 {len(items)} 项:" + "、".join(summary_parts) if items else "未找到相关信息"

        return {
            "summary": summary,    # "共 6 项:排班 3 条、会议 2 条、公告 1 条"
            "items": items,        # 前端 <AggregatedDayCard> 直接渲染
            "total_count": len(items),
            "module_counts": module_counts,  # {排班: 3, 会议: 2, 公告: 1}
        }
```

**前端消费协议:** `module_counts` 用于 SwitchBoard 标签数;`items[].module` 用于分组渲染;`items[].sort_key` 与排序无关(已排好),仅用于日志诊断。

### 4.5 工具 `execute` 签名升级示例

```python
# schedule_tool.py
class ScheduleTool(BaseTool):
    intent_type = "schedule_query"

    def build_base_queryset(self):
        return Schedule.objects.select_related("user", "shift").all()

    def _scope_self(self, qs, ctx):
        return qs.filter(user=ctx.user)

    def _scope_department(self, qs, ctx):
        return qs.filter(user__department=ctx.user.department)

    def execute(self, params: dict, scope: SmartAssistantScope, qs) -> dict:
        # qs 已被 scope 过滤;此处只做关键词/排序/序列化
        ...
```

---

## 5. 数据流(典型场景)

### 5.1 用户问"这周我有哪些事"

1. **入口:** `POST /api/smart-assistant/chat/ {message: "这周我有哪些事"}`
2. **IntentClassifier:** 返回 `needs_multi_tool=True`,`candidate_tools=[schedule_query, meeting_room_query, announcement_query]`
3. **ToolChainPlanner:** LLM 生成 3 步骤计划
4. **ToolChainExecutor:**
   - 对每步:`ToolContext.from_request(request)` → `scope` 由 `resolve_scope()` 自动派生
   - 调 `tool.build_base_queryset()` → 调 `tool.get_queryset_for_scope(base_qs, ctx)` → 调 `tool.execute(params, scope, qs)`
5. **ResultSynthesizer:** 聚合 3 个工具结果,按时间排序,输出结构化 JSON
6. **LLM 合成:** 输入结构化 JSON,输出自然语言 + Markdown
7. **前端:** 顶部 LLM 回答 + 下方 `<AggregatedDayCard items={...}>`

### 5.2 边界:权限降级

- **普通员工** 问 "全公司本周安排"
- ToolChainPlanner 仍规划 3 个工具
- 工具 scope=SELF,只返回本人数据
- LLM 合成时附"提示:你只能查看与你相关的内容,如需全公司数据请联系管理员"

---

## 6. 错误处理

### 6.1 工具执行异常

| 失败 | 处理 |
|---|---|
| 单工具 `DatabaseError` | 该工具结果替换为 `{"found": False, "reason": "db_error"}`,其他工具继续 |
| 单工具超时(>5s) | `concurrent.futures` + `future.result(timeout=5)`,同 db_error 处理 |
| 所有工具失败 | `ResultSynthesizer` 检测后返回"暂无法获取信息,请稍后再试" |

**降级原则:** 一个工具挂掉 ≠ 整个回答失败。

### 6.2 权限拒绝

| 场景 | 处理 |
|---|---|
| 用户未登录访问 | 401 中间件(已有) |
| 工具 `required_auth=True` 但 user 未认证 | `ToolRegistry.get_tool_for_user()` 返回 `None`,跳过 |
| scope=SELF 但工具未实现 `_scope_self` | 启动时 `check_tool_scopes` 校验失败,代码**无法启动** |
| 用户无权限的意图(如员工问"管理员后台") | IntentClassifier 置信度低 → 走"反问澄清"分支(已有) |

### 6.3 缓存一致性

| 维度 | 策略 |
|---|---|
| 同 query 完全相同 | 命中"回答缓存"(2h TTL) |
| 同用户不同时间窗口 | **不缓存**(query 字符串包含时间,哈希自然区分) |
| scope 变化(管理员降级) | 缓存 key 包含 `user_id + scope`,自动失效 |
| DB 写入后排班变更 | 不主动失效,2h 自然过期(可接受偏差) |

### 6.4 LLM 路由错误

- IntentClassifier 误判 → 工具仍按 plan 执行,LLM 兜底
- ToolChainPlanner JSON 解析失败 → 已有 fallback:用 IntentClassifier 的 `candidate_tools` 作为单步计划
- ResultSynthesizer 输出超长 → 截断 2000 字 + 提示"详见原始数据"

---

## 7. 测试策略

### 7.1 单元测试(+43 个)

| 文件 | 用例数 | 覆盖点 |
|---|---|---|
| `tests/test_scope.py` (新) | 8 | `SmartAssistantScope` 枚举、`resolve_scope()` 三种用户派生 |
| `tests/test_tool_context.py` (扩展) | +3 | scope 自动填充、`from_request` |
| `tests/test_base_tool.py` (新) | 6 | 抽象方法、SELF/DEPT/GLOBAL 三路径、`_scope_self` NotImplementedError |
| `tests/test_meeting_room_tool.py` (扩展) | +5 | 三种 scope 差异 |
| `tests/test_schedule_tool.py` (扩展) | +5 | 同上 |
| `tests/test_announcement_tool.py` (扩展) | +4 | 同上 + 部门过滤 |
| `tests/test_result_synthesizer.py` (新) | 10 | 聚合/排序/合并/空降级/跨模块 summary |

### 7.2 集成测试(+13 个)

| 文件 | 用例数 | 覆盖点 |
|---|---|---|
| `tests/test_tool_chain_executor.py` (新) | 8 | scope 注入、单失败不影响整体、超时、权限拒绝 |
| `tests/test_orchestrator_integration.py` (新) | 5 | 员工/主管/管理员三身份端到端 |

### 7.3 E2E 测试(+4 个)

| 场景 |
|---|
| 员工问"我今天的事" → 本人数据 |
| 主管问"本部门本周" → 部门数据 |
| 管理员问"全公司本周" → 全量 |
| 权限边界:员工问"全公司公告" → 收到降级提示 |

### 7.4 启动时校验(+5 个 cmd 测试)

```
$ python manage.py check_tool_scopes
✅ All 13 tools implement build_base_queryset
✅ All 13 tools implement _scope_self
EXIT 0
```

CI 步骤:`python manage.py check_tool_scopes` 失败则整个 build 失败。

### 7.5 前端测试(+10 个)

- `AggregatedDayCard.test.jsx`(+6):渲染、跨模块分组、空 items、骨架、错误态
- `quickCommands.test.js`(+4):新增"我的本周"快捷指令触发 `personal_summary`

### 7.6 覆盖率门槛

| 模块 | 当前 | 目标 |
|---|---|---|
| `scope.py`(新) | — | 100% |
| `result_synthesizer.py`(新) | — | ≥ 90% |
| `tools/base.py` | 48% | ≥ 85% |
| 三个工具(schedule/meeting/announcement) | 33-39% | ≥ 85% |
| **`smart_assistant` 模块总覆盖率** | **63.25%** | **≥ 85%** |

### 7.7 不测什么(YAGNI)

- ~~预聚合~~
- ~~写操作~~
- ~~主动推送~~
- ~~多语言~~(项目硬约束 i18n zh-hans)

---

## 8. 风险与依赖

| 风险 | 等级 | 缓解 |
|---|---|---|
| 工具 `_scope_self` 未实现导致线上越权 | **HIGH** | 启动时 `check_tool_scopes` 强制校验,CI 跑 |
| `BaseTool` 抽象方法引入破坏现有 12 个工具 | **HIGH** | TDD 顺序:先加抽象 → 跑全套测试看到底有多少工具 break → 全部 13 个工具补齐 `build_base_queryset` + `_scope_self`(很多是 1 行代码) → 3 个核心工具再升级 `execute` 签名 |
| LLM 不识别"汇总"意图,仍路由到单工具 | MEDIUM | prompt_builder 强化描述 + E2E 验证 |
| N+1 查询(ComplianceTool 等) | MEDIUM | 现有测试已覆盖,新测试加 `CaptureQueriesContext` 断言 |
| ResultSynthesizer 输出格式与前端不一致 | MEDIUM | 前后端联合评审 schema,前后端测试覆盖 |
| 缓存键设计错误导致跨用户泄露 | **HIGH** | 缓存 key 包含 `user_id + scope`,单元测试覆盖 |
| 三个工具 `execute` 签名升级破坏外部调用 | LOW | 仅 `smart_assistant` 内部使用,无外部 API |

### 依赖

**后端:**
- 已有:`django`、`djangorestframework`、`pytest`、`pytest-django`、`concurrent.futures`(内置)
- 新增:`smart_assistant.view_department` 和 `smart_assistant.view_global` 两个 Django permission(在 migration 中创建)

**前端:**
- 已有:`React 18.3`、`Ant Design 5`、`react-query v5`
- 无新增依赖

**数据源:**
- 已有:`events.Schedule`、`meeting_rooms.Booking`、`communication.Post` 等模型

---

## 9. 实施步骤(分阶段)

### 阶段 1:基础设施(1 天)— P0

- [ ] 新增 `scope.py` + `SmartAssistantScope` 枚举 + `resolve_scope()`
- [ ] `ToolContext` 增加 `scope` 字段
- [ ] 跑 baseline 测试:记录当前多少工具缺 `_scope_self`(预计 3 个)

### 阶段 2:BaseTool 抽象升级 + 全 13 工具补齐 _scope_self(1 天)— P0

- [ ] `BaseTool` 增加 `build_base_queryset` / `get_queryset_for_scope` / `_scope_self` 三个抽象方法
- [ ] 跑全套测试:看到底多少工具 break(预计 12 个旧工具)
- [ ] **全部 13 个工具补齐 `build_base_queryset` + `_scope_self`**(很多简单工具如 `MemoTool` 一行即可:`def _scope_self(self, qs, ctx): return qs.filter(author=ctx.user)`)
- [ ] 跑 `check_tool_scopes` 验证全部通过

### 阶段 3:三个核心工具升级 `execute` 签名(2 天)— P0

- [ ] `ScheduleTool` `execute` 改签名为 `(self, params, scope, qs)`,内部用传入的 `qs` 而非自己 `Model.objects.all()`
- [ ] `MeetingRoomTool` 同上
- [ ] `AnnouncementTool` 同上
- [ ] 每个工具 ≥ 5 个测试(scope 差异 + 关键词 + 排序)
- [ ] **关键回归测试:** 旧调用方式 `tool.execute(query, ctx)` 必须仍工作(向后兼容)

### 阶段 4:ResultSynthesizer(1.5 天)— P1

- [ ] 新增 `agent/result_synthesizer.py`
- [ ] 实现 `synthesize()`:时间排序/同主题合并/跨模块 summary
- [ ] 接入 `Orchestrator` 替换原有单工具返回路径
- [ ] 10 个单元测试覆盖排序/合并/空降级

### 阶段 5:启动校验 + CI(0.5 天)— P0

- [ ] 新增 `management/commands/check_tool_scopes.py`
- [ ] `apps.py` `ready()` 钩子在 DEBUG=True 时调用
- [ ] `.github/workflows/ci.yml` 增加 `python manage.py check_tool_scopes` 步骤
- [ ] 5 个 cmd 测试

### 阶段 6:集成 + E2E 测试(1.5 天)— P1

- [ ] `test_tool_chain_executor.py` 8 个测试(scope 注入/降级/超时)
- [ ] `test_orchestrator_integration.py` 5 个测试(三身份端到端)
- [ ] `test_e2e_smart_chat.py` 4 个测试(员工/主管/管理员/降级提示)

### 阶段 7:Prompt 强化 + 前端(1.5 天)— P1

- [ ] `prompt_builder.py` 追加"汇总场景"提示
- [ ] 新增 `<AggregatedDayCard>` 组件 + 6 个测试
- [ ] `quickCommands` 新增"我的本周"快捷指令 + 4 个测试
- [ ] `ToolResult.jsx` 注册新组件

### 阶段 8:联调 + 文档 + PR(1 天)— P0

- [ ] 跑后端全套测试,目标覆盖率 ≥ 85%
- [ ] 跑前端 `npm test`
- [ ] `ruff check` + ESLint 0 警告
- [ ] 文档:在 `docs/technical/16-smart-assistant.md` 追加"分层权限与跨模块汇总"章节
- [ ] 文档:`docs/user-manual/08-smart-assistant-usage.md` 追加用户视角说明
- [ ] PR + CI + Review

---

## 10. 验收标准

- [ ] `SmartAssistantScope` + `resolve_scope()` 实现 + 8 个测试通过
- [ ] `BaseTool` 抽象方法升级,**全部 13 个工具**实现 `_scope_self`,0 回归(`check_tool_scopes` 校验通过)
- [ ] 三个核心工具(Schedule/MeetingRoom/Announcement)升级 `execute` 签名,≥ 14 个新测试通过
- [ ] 旧 `execute(query, ctx)` 调用方式仍工作(向后兼容)
- [ ] `ResultSynthesizer` 实现,10 个测试通过,Orchestrator 接入
- [ ] `check_tool_scopes` 命令 + CI 集成,5 个测试通过
- [ ] 集成测试 13 个 + E2E 测试 4 个全部通过
- [ ] `smart_assistant` 模块覆盖率 ≥ 85%
- [ ] `AggregatedDayCard` 前端组件 + 10 个测试通过
- [ ] 后端 ruff + 前端 ESLint 0 警告
- [ ] 文档已更新(技术手册 + 用户手册)
- [ ] PR 已开,CI 全绿,Review 通过

---

## 11. 边界(明确不做的事)

- ❌ 写操作(代用户创建/预约/发布) — 后续独立项目
- ❌ 主动推送(Celery Beat + 通知) — 后续独立项目
- ❌ 预聚合 / 物化视图 — 用户明确选择"先实时后续优化"
- ❌ 个人仪表盘 widget — 独立前端项目
- ❌ Dify / RAGFlow 接入改造 — 已有,不影响
- ❌ 多语言(i18n zh-hans 项目硬约束)
- ❌ 微服务 / 前后端分离重构
- ❌ LLM 底座升级(deepseek-r1:1.5b → 更大模型)
- ❌ 多模态(图像/语音输入)

---

## 12. 后续演进(明确不在本期,但保留接口)

当出现以下信号时,再考虑升级:
1. **预聚合** — 用户体感 P95 > 2s 持续 2 周以上
2. **写操作** — 出现"代预约会议室"业务需求时
3. **主动推送** — 出现"每日早晨播报"产品需求时
4. **个人仪表盘** — 出现"首页 widget"产品需求时

这些演进通过 ResultSynthesizer 接口稳定隔离,新功能可在不破坏现有 API 的前提下叠加。
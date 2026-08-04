# Design: swap_request 工具业务逻辑补全

**Date**: 2026-08-04
**Status**: Draft (awaiting user review)
**Author**: Claude (via brainstorming)
**Branch**: main (续 PR #175)

## 1. 背景 & 目标

### 1.1 背景

PR #171 / #174 / #175 已合并:

| PR | 内容 |
|---|---|
| #171 | cryptography 50.0.0(CVE-2026-69247 修复) |
| #174 | confirm-replay 框架 Phase A-D + 38 单测 |
| #175 | 换班工具骨架 + 10 单测 |

**当前状态**:`SwapRequestCreateTool` / `SwapRequestDecideTool` 仍是占位实现,`_dry_run` / `_confirmed` 方法体只有 TODO 注释,返回 `not_implemented` 字符串。骨架已就绪,业务逻辑待补全。

### 1.2 目标

补全两个 write 工具的真实业务逻辑,使 confirm-replay 流程在换班场景下端到端可用:

1. **自然语言解析**:中文 query → 结构化参数(接收方姓名 / 日期 / 动作 / swap_id)
2. **业务逻辑复用**:不再在工具内重写,改为抽到 `events/services/swap_service.py`,ViewSet 调 service,工具也调 service(零逻辑分叉)
3. **dry_run 早期拒绝**:解析失败 / 业务校验失败 → 返回 `found=False`,不让用户进入确认弹窗
4. **LLM 失败兜底**:LLM 不可用/超时/非法 JSON → 返回 `found=False`,不降级到规则
5. **API 行为不变**:ViewSet HTTP 行为零变化,只迁移内部实现

### 1.3 不在范围(YAGNI)

- LLM 反复追问多轮澄清
- 接收方 reject → 通知申请方(走现有通知机制,不在本次范围)
- 双向对调(target_schedule 字段)解析,本次只支持单方面替班
- 移动端 / WebSocket 推送

## 2. 架构

```
                            ┌──────────────────────────────────────┐
   user_query ─────────►   │ SwapRequestCreateTool.execute        │
                            │   │ dry_run                           │
                            │   ├─► SwapExtractor.extract_create   │
                            │   │       │ LLMClient (existing)      │
                            │   │       ▼                          │
                            │   │   parsed_params (or None)        │
                            │   │       │                          │
                            │   │       ▼                          │
                            │   │   dry_run 校验:                  │
                            │   │   target 是否存在 / 该日是否有班  │
                            │   │       │                          │
                            │   │       ▼                          │
                            │   │   draft (or found=False)         │
                            │   ├─► confirm-replay 缓存 (Phase A)  │
                            │   ▼                                  │
                            │ confirmed                            │
                            │   ├─► SwapExtractor.extract_create   │
                            │   ├─► SwapService.create_swap        │
                            │   │       │ Django ORM +             │
                            │   │       │ transaction.atomic       │
                            │   │       ▼                          │
                            │   │   ScheduleSwapRequest saved      │
                            │   ▼                                  │
                            │ answer: summary + result            │
                            └──────────────────────────────────────┘
```

**关键约束**:
- 工具层薄:只做"解析 + 调 service + 包装结果"
- Extractor 独立:可单测、可替换 LLM、可换模型
- Service 独立:纯业务,工具 / HTTP / CLI 任何入口都能用
- 复用率:ViewSet → service 100% 复用 → 工具间接继承

## 3. 组件

### 3.1 `events/services/swap_service.py`(新文件)

把 ViewSet 内的 4 个动作提到 service 层,签名用 plain Python(不依赖 DRF Request):

```python
# events/services/swap_service.py
class SwapServiceError(Exception):
    """业务错误(非用户/权限),由调用方转为 HTTP 400/409"""

class SwapPermissionError(Exception):
    """权限错误(用户没关联 personnel / 不是接收方/申请方)"""

class SwapNotFoundError(Exception):
    """swap_id 不存在"""

def create_swap_from_serializer(*, serializer) -> ScheduleSwapRequest:
    """从已校验的 serializer 创建 swap(供 ViewSet 使用)。"""

def create_swap_by_query(*, requester: Personnel, target_name: str,
                         duty_date: date, reason: str = "") -> ScheduleSwapRequest:
    """从自由文本创建 swap(供工具使用,内部先解析再落库)。"""

def accept_swap(*, actor: User, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 accept。"""

def reject_swap(*, actor: User, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 reject。"""

def cancel_swap(*, actor: User, swap_id: int) -> ScheduleSwapRequest:
    """申请方 cancel。"""
```

**create_swap_from_serializer 内部步骤**:
1. 从 `serializer.validated_data["requester"]` / `original_schedule` / `target_personnel`(已注入)
2. 构造 `ScheduleSwapRequest`
3. `instance.full_clean()`(使用模型已有的 clean() 校验)
4. `save()`(在 `transaction.atomic()` 内)

**create_swap_by_query 内部步骤**:
1. `Personnel.objects.filter(name=target_name).first()` 找 target
2. `Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first()` 找 schedule
3. 校验 target_personnel != requester
4. 调 `_create_swap_internal`

**accept_swap / reject_swap / cancel_swap 步骤**:
1. `get_object_or_404` 查 swap
2. 校验权限(actor 是 target_personnel 的 user_account / 是 requester)
3. 校验 `status == STATUS_PENDING`
4. 调 `swap.apply_swap(approver=...)`(accept) 或直接改字段(reject/cancel)
5. 写 `ScheduleSwapAuditLog`
6. 全部在 `transaction.atomic()` 内

### 3.2 `events/views/swap.py`(修改)

```python
def perform_create(self, serializer):
    """薄包装:调 service,把异常转 DRF 异常。"""
    try:
        instance = swap_service.create_swap_from_serializer(serializer=serializer)
    except SwapPermissionError as e:
        raise PermissionDenied(str(e))
    except SwapServiceError as e:
        raise DRFValidationError({"detail": str(e)})

@action(detail=True, methods=["post"])
def accept(self, request, pk=None):
    try:
        swap = swap_service.accept_swap(
            actor=request.user, swap_id=pk,
            note=request.data.get("target_decision_note", "接收方同意"),
        )
    except SwapNotFoundError:
        return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
    except SwapPermissionError as e:
        raise PermissionDenied(str(e))
    except SwapServiceError as e:
        return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
    return Response(SwapRequestDetailSerializer(swap).data)
```

**目标**:HTTP 行为完全不变(序列化器、状态码、错误码不动)。

### 3.3 `smart_assistant/extractors/swap_extractor.py`(新文件)

```python
# smart_assistant/extractors/swap_extractor.py
from dataclasses import dataclass

@dataclass
class CreateParams:
    target_name: str          # 必填
    duty_date: str            # YYYY-MM-DD,必填
    reason: str = ""          # 可选

@dataclass
class DecideParams:
    action: str               # "accept" | "reject" | "cancel"
    swap_id: int              # 必填
    note: str = ""            # 可选

def extract_create_params(query: str, requester: Personnel) -> CreateParams | None:
    """调 LLM 提取 create 参数。LLM 失败/缺字段 → None。"""

def extract_decide_params(query: str, actor: User) -> DecideParams | None:
    """调 LLM 提取 decide 参数。同上失败语义。"""
```

**LLM 调用鲁棒性**(在 `_call_llm_for_json` 中):

```python
def _call_llm_for_json(prompt: str) -> dict | None:
    raw = _call_llm(prompt)  # 现有 LLM 客户端
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
```

### 3.4 `smart_assistant/extractors/prompts/swap_*.py`(新文件)

两个 prompt 模板(cn):

- `swap_create_prompt.py`:`SWAP_CREATE_SYSTEM_PROMPT` + `build_create_user_prompt(query, requester_name, today)`
- `swap_decide_prompt.py`:`SWAP_DECIDE_SYSTEM_PROMPT` + `build_decide_user_prompt(query, actor_name, pending_swaps)`

Prompt 关键约束:
1. 角色:你是 swap_request_extractor,只输出 JSON
2. input: query + requester.name + 当前日期
3. schema 严格给出字段
4. 输出严格 JSON,格式样例
5. 不可推断字段填 `null`

### 3.5 `smart_assistant/tools/swap_request_tool.py`(修改)

```python
def _dry_run(self, query, ctx) -> dict:
    user = ctx.get("user")
    requester = user.personnel
    if not requester:
        return {"found": False, "message": "当前用户未关联人员档案"}

    params = extract_create_params(query, requester)
    if params is None:
        return {"found": False, "message": "无法识别换班意图,请明确换班对象(姓名)和日期"}

    target = Personnel.objects.filter(name=params.target_name).first()
    if not target:
        return {"found": False, "message": f"未找到 '{params.target_name}' 该人员"}

    duty_date = parse_date(params.duty_date)  # 鲁棒性:接受 "X月X日" / "2026-08-12"
    if not duty_date:
        return {"found": False, "message": f"无法解析日期 '{params.duty_date}'"}

    schedule = Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first()
    if not schedule:
        return {"found": False, "message": f"找不到您 {duty_date} 的排班记录"}

    if target.id == requester.id:
        return {"found": False, "message": "不能把班换给自己"}

    return {
        "found": True,
        "draft": {
            "summary": f"为 {requester.name} → {target.name} {duty_date} 发起换班申请",
            "fields": {
                "target_personnel_id": target.id,
                "target_personnel_name": target.name,
                "original_schedule_id": schedule.id,
                "duty_date": duty_date.isoformat(),
                "reason": params.reason,
            },
        },
    }

def _confirmed(self, query, ctx) -> dict:
    """confirmed:重 parse query,直接调 service。"""
    user = ctx.get("user")
    requester = user.personnel
    if not requester:
        return {"found": False, "message": "当前用户未关联人员档案"}

    params = extract_create_params(query, requester)
    if params is None:
        return {"found": False, "message": "无法识别换班意图"}

    try:
        swap = swap_service.create_swap_by_query(
            requester=requester,
            target_name=params.target_name,
            duty_date=parse_date(params.duty_date),
            reason=params.reason,
        )
    except (SwapServiceError, SwapPermissionError) as e:
        return {"found": False, "message": str(e)}

    return {
        "found": True,
        "result": {"swap_id": swap.id, "status": swap.status},
        "summary": f"换班申请已发起: #{swap.id} {requester.name} → {swap.target_personnel.name} {swap.original_schedule.duty_date}",
    }
```

**Decide 工具类似**(extract_decide_params → 验 swap_id / 权限 / 状态 → dry_run 返 draft,confirmed 调 service)。

**view 层需要注入 ctx.user**:当前 view 在 replay 路径上 `context={"history": [], "confirmed": True, "confirm_token": confirm_token}` 没传 user。改造方案:view 层改为 `context={"history": [], "confirmed": True, "confirm_token": confirm_token, "user": request.user}`,其他路径同理。

### 3.6 性能

- **dry_run 阶段**:走 LLM 解析 → ~1-2s 延迟(用户预期)
- **confirmed 阶段**:ViewSet 在 replay 路径上从 `draft_entry["draft"]` 拿到 fields,工具 `_confirmed` 优先用 `ctx.get("draft_fields")`,LLM 仅在 draft_fields 缺失时回退。否则一次换班 = 2 次 LLM 调用,延迟翻倍(2-4s)

### 3.7 缓存与幂等

- draft 缓存已经走 `set_confirmation_draft` (Phase A-D),`_dry_run` 只返回 dict 给 orchestrator
- `confirmed` 路径 priority: 1) ctx.draft_fields(来自缓存) → 2) 重 parse(LLM)
- 同一 reason 的重复请求:靠 `UniqueConstraint(original_schedule, status=pending)` 兜底
- 若 replay 路径 service 报 UniqueConstraint 违反(draft 期间已被并行创建),转 `found=False, message="该排班已有进行中的换班申请"`

## 4. 数据流

### 4.1 Create 流程

```
1. User: "我想和李四换下周三的班"
2. SwapRequestCreateTool.execute(dry_run=True)
   ├─ extract_create_params(query, requester) → {target_name:"李四", duty_date:"2026-08-12", reason:""}
   ├─ Personnel.objects.filter(name="李四") → hit
   ├─ Schedule.objects.filter(duty_date="2026-08-12", duty_person=requester) → hit
   └─ return draft{summary, fields}
3. orchestrator 存 draft + 返 confirmation_token
4. Frontend Modal 显示 summary,用户确认
5. Frontend POST /api/chat {query, confirm_token}
6. ViewSet 走 replay 路径,调 SwapRequestCreateTool.execute(confirmed=True)
   ├─ 重 parse(LLM) → 同 params
   ├─ swap_service.create_swap_by_query(requester, params)
   │   ├─ 校验 target_personnel != requester
   │   ├─ 构造 ScheduleSwapRequest(requester, original_schedule, target_personnel, reason, expires_at)
   │   ├─ instance.full_clean()
   │   └─ save() 在 transaction.atomic 内
   └─ return {found:True, result:{swap_id:7, status:"pending"}, summary:...}
7. ViewSet 返 200 + answer
```

### 4.2 Decide 流程

```
1. User: "同意张三的换班申请"
2. SwapRequestDecideTool.execute(dry_run=True)
   ├─ extract_decide_params(query, actor) → {action:"accept", swap_id:??, note:""}
   │  注:swap_id 用 LLM 提取可能不靠谱 → 兜底:找 actor 作为 target_personnel 的最新 pending 申请
   ├─ 校验:actor.user_account == swap.target_personnel.user_account
   ├─ 校验:swap.status == pending
   └─ return draft{summary: "确认接受 #7 张三 → 您 2026-08-12 换班"}
3. ... 同 create 流程
4. swap_service.accept_swap(actor, swap_id, note): 调 swap.apply_swap + 写 audit_log
```

## 5. 错误处理

| 场景 | 路径 | 返回 |
|---|---|---|
| LLM 解析失败 | `extract_create_params` → None | `{"found": False, "message": "无法识别换班意图,请明确换班对象(姓名)和日期"}` |
| 目标人不存在 | dry_run 校验 | `{"found": False, "message": "未找到 'XXX' 该人员"}` |
| 不是申请方排班 | dry_run 校验 | `{"found": False, "message": "找不到您 X 月 X 日的排班"}` |
| 自己换自己 | dry_run 校验 | `{"found": False, "message": "不能把班换给自己"}` |
| 同步创建失败(SwapServiceError / SwapPermissionError) | service 抛 → 工具 catch | `{"found": False, "message": str(e)}` |
| 重复 draft(UniqueConstraint 违反) | service 抛 → 工具 catch | `{"found": False, "message": "该排班已有进行中的换班申请"}` |
| 已过期 token | 现有 ViewSet 处理(410 Gone) | 同上 |
| wrong user(replay token 跨用户) | 现有 ViewSet 处理(403) | 同上 |

## 6. 测试

### 6.1 新增/修改测试

| 文件 | 类型 | 数量 | 内容 |
|---|---|---|---|
| `events/tests/test_swap_service.py` | 新 | ~15 | service 4 函数 × 3-5 case |
| `smart_assistant/tests/test_swap_extractor.py` | 新 | ~8 | 2 extractor × 3-4 case (mock LLM) |
| `smart_assistant/tests/test_swap_request_tool.py` | 改 | +12 | 现有 6 case + 新增 dry_run 校验 / confirmed 落库 |
| `events/tests/test_swap_request_api.py` | 回归 | 现有 | 验证 0 退化(API 行为不变) |

### 6.2 Mock 策略

- LLM 客户端:patch `smart_assistant.extractors.swap_extractor._call_llm`
- service 直接调真 ORM(在 `pytest --ds=...test` in-memory SQLite 中跑)

### 6.3 覆盖率目标

80%+(与项目标准一致)

## 7. 迁移 / 兼容性

| 改动 | 兼容情况 |
|---|---|
| ViewSet 内部调 service | HTTP 行为完全不变(序列化器、状态码、错误码不动) |
| 新增 `events/services/` | 全新增,旧 import 路径不变 |
| 新增 `smart_assistant/extractors/` | 全新增,工具改用新路径 |
| 工具类 `execute` 签名 | 已兼容(现有 if dry_run/confirmed 逻辑保留) |
| 测试 fixtures | 现有 `swap_request` fixture 复用 |
| `requirements.in` | 不变(LLM 客户端已存在) |

## 8. 风险

| 风险 | 缓解 |
|---|---|
| LLM JSON 解析鲁棒性 | `_call_llm_for_json` try/except + 正则提取 `{}` + 字段校验 |
| LLM 幻觉 swap_id | decide 用"name + 日期"做兜底查找最近 pending 申请 |
| ViewSet 改造影响 API 集成测试 | 跑 `events/tests/test_swap_request_api.py` 验证 0 退化 |
| service 内的 `transaction.atomic()` 与 LLM 跨调用 | 严格:`create_swap` LLM 不在事务内,事务只包 save;`apply_swap` 已有原子性 |
| cache draft 与 personnel 状态变更 | TTL 10 分钟兜底,过期重 parse |
| replay 路径缺少 ctx.user | view 层在 `context` dict 注入 `user=request.user` |
| dry_run 校验与 confirmed 实际执行分叉 | service 内部再校验一次,失败 → 返 found=False |

## 9. 实施步骤

| # | 步骤 | 验证 |
|---|---|---|
| 1 | 创建 `events/services/__init__.py` + `swap_service.py` | `python -c "import events.services.swap_service"` |
| 2 | 抽出 `create_swap_from_serializer` / `accept_swap` / `reject_swap` / `cancel_swap` | `pytest events/tests/test_swap_service.py -v` |
| 3 | 改 `events/views/swap.py` 4 个动作为薄包装 | `pytest events/tests/test_swap_request_api.py -v`(API 0 退化) |
| 4 | 创建 `smart_assistant/extractors/__init__.py` + `prompts/__init__.py` | `import` 测试 |
| 5 | 写 `swap_create_prompt.py` + `swap_decide_prompt.py` | 手工检查 prompt 模板 |
| 6 | 写 `swap_extractor.py` + `_call_llm_for_json` | `pytest test_swap_extractor.py -v` |
| 7 | 改 `swap_request_tool.py` `_dry_run` / `_confirmed` 用 ext + service | `pytest test_swap_request_tool.py -v` |
| 8 | 改 `smart_assistant/views/chat.py` 在 replay 路径注入 `user` | `pytest test_view_confirm_replay.py -v` |
| 9 | 跑全套:backend `pytest`,前端不动 | 全绿 |
| 10 | 跑 `pytest --cov=events.services --cov=smart_assistant.extractors --cov=smart_assistant.tools.swap_request_tool` | coverage ≥ 80% |
| 11 | ruff check + mypy | 0 错误 |
| 12 | 提交 + PR | 走 confirm-replay 框架 PR 流程 |

## 10. 附录:文件清单

| 路径 | 操作 | 估行数 |
|---|---|---|
| `omni_desk_backend/events/services/__init__.py` | 新 | 5 |
| `omni_desk_backend/events/services/swap_service.py` | 新 | ~180 |
| `omni_desk_backend/events/views/swap.py` | 改 | +20 -50(净改) |
| `omni_desk_backend/smart_assistant/extractors/__init__.py` | 新 | 5 |
| `omni_desk_backend/smart_assistant/extractors/swap_extractor.py` | 新 | ~150 |
| `omni_desk_backend/smart_assistant/extractors/prompts/__init__.py` | 新 | 5 |
| `omni_desk_backend/smart_assistant/extractors/prompts/swap_create_prompt.py` | 新 | ~50 |
| `omni_desk_backend/smart_assistant/extractors/prompts/swap_decide_prompt.py` | 新 | ~50 |
| `omni_desk_backend/smart_assistant/tools/swap_request_tool.py` | 改 | +120 -20 |
| `omni_desk_backend/smart_assistant/views/chat.py` | 改 | +2 / -0 |
| `omni_desk_backend/events/tests/test_swap_service.py` | 新 | ~250 |
| `omni_desk_backend/smart_assistant/tests/test_swap_extractor.py` | 新 | ~120 |
| `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py` | 改 | +250 |

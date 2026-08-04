# 智能助手 confirm-replay 框架补全

| 项目 | 内容 |
|---|---|
| 日期 | 2026-08-04 |
| 作者 | Claude（人工指令触发） |
| 状态 | ⏳ 草案，待用户审批 |
| 分支 | `feat/sa-confirm-framework`（基于 `feat/sa-swap-shift` 的调研结论） |
| 上游消费者 | `feat/sa-swap-shift`（换班工具需要此框架） |
| 优先级 | **P0** —— swap 工具与未来所有 write 工具的先决条件 |

---

## 1. 背景与目标

### 1.1 现状（2026-08-04 调研结论）

| 层 | 现状 |
|---|---|
| `Reject` 数据类 | ✅ 已定义（`hooks/base.py:43-55`） |
| `HookRegistry.run_pre_hooks` | ✅ 接受 Reject 短路返回（`hooks/base.py:273-305`） |
| `wiring.execute_guarded` | ❌ 不调 `run_pre_hooks`，直接 `tool.execute()` |
| `AgentOrchestrator.process()` / `process_stream()` | ❌ 不读 `tool.require_confirmation`，不调 pre-hook 链 |
| `SmartChatViewSet.create` / `stream` | ❌ 无 `confirm_token` / replay 入口 |
| `BaseTool.require_confirmation` 文档注释 | ⚠️ 引用 `Reject(error_code="confirmation_required")` 挂起执行——**只是设计意图** |

### 1.2 目标

补齐三处缺失，使所有未来 write 工具都能声明 `require_confirmation = True`，框架自动完成：

```
用户首次请求 → 工具.execute → pre-hook 返回 Reject(confirmation_required)
            → orchestrator 不调 LLM，把 draft 存缓存，返回 awaiting_confirmation
            → 前端 QuickAssistant 弹 Modal.confirm
            → 用户确认 → 二次请求带 confirm_token
            → 视图层检测 token + 缓存命中 → 跳过 pre-hook 链，直接 tool.execute 落库
            → 返回最终结果给前端
```

### 1.3 非目标

- ❌ 不引入新 hook 类型（复用现有 `Reject`）
- ❌ 不动 `BaseTool` 接口签名
- ❌ 不动 orchestrator 已有的多工具链式路径（仅单工具路径）
- ❌ 不动 `SmartChatViewSet.stream`（流式路径与 confirm 流程冲突太大，本期跳过）

---

## 2. 涉及文件

| 文件 | 改动类型 |
|---|---|
| `smart_assistant/hooks/wiring.py` | 新增 `apply_pre_execute_hooks` 同步入口 |
| `smart_assistant/cache.py` | 新增 `set/get/clear_confirmation_draft` 三个函数 |
| `smart_assistant/agent/orchestrator.py` | 单工具路由段（process + process_stream）插入拦截 |
| `smart_assistant/views/chat.py` | `SmartChatViewSet.create` 检测 confirm_token 分支 |
| `smart_assistant/serializers.py` | `SmartChatRequestSerializer` 新增 `confirm_token` 字段 |
| `smart_assistant/tests/test_confirm_replay_e2e.py` | 新增端到端测试 |
| `smart_assistant/tests/test_wiring_pre_execute.py` | 新增 `apply_pre_execute_hooks` 单测 |
| `smart_assistant/tests/test_cache_confirmation_draft.py` | 新增 draft 缓存单测 |
| `smart_assistant/tests/test_orchestrator_confirm.py` | 新增 orchestrator 拦截单测 |
| `docs/technical/16-smart-assistant.md` 或相应章节 | 功能完成后追加"confirm-replay 框架"小节 |

---

## 3. 技术方案

### 3.1 wiring.py 新增 `apply_pre_execute_hooks`

**参考** `apply_post_execute_hooks`（`wiring.py:125-141`）的 `_run_coroutine_sync` 模式。

```python
def apply_pre_execute_hooks(tool: Any, ctx: Any, params: dict) -> dict | Reject:
    """同步执行全局 PRE_EXECUTE 钩子链。

    返回:
        dict: 最终参数（可能被多个 Hook 修改）
        Reject: 被某个 Hook 拒绝（通常是 require_confirmation=True 的工具）

    失败安全：无 pre 钩子时走快速路径直接返回 params；钩子链异常降级为透传，
    不影响主流程。
    """
    registry = get_registry()
    if not registry.list_hooks(HookEvent.PRE_EXECUTE):
        return params  # 快速路径：无 pre 钩子
    return _run_coroutine_sync(
        lambda: registry.run_pre_hooks(tool, ctx, params),
        "PRE_EXECUTE 钩子链",
        params,
    )
```

### 3.2 cache.py 新增 draft 三件套

```python
CONFIRMATION_DRAFT_TTL = 600  # 10 分钟

def _draft_key(token: str) -> str:
    return _key("confirm_draft", token)


def set_confirmation_draft(token: str, draft: dict, ttl: int = CONFIRMATION_DRAFT_TTL) -> None:
    """存 confirmation draft。token 由调用方生成（uuid4）。"""
    cache.set(_draft_key(token), draft, ttl)


def get_confirmation_draft(token: str) -> dict | None:
    """取 confirmation draft。过期/不存在返回 None。"""
    return cache.get(_draft_key(token))


def clear_confirmation_draft(token: str) -> None:
    """replay 成功后清理 draft，防止 token 重放。"""
    cache.delete(_draft_key(token))
```

### 3.3 orchestrator 接入 confirm 拦截

在 `orchestrator.process()` 单工具路由段（`orchestrator.py:177-251`）的 `execute_guarded` 之前插入：

```python
tool = ToolRegistry.get_tool(intent)
if tool:
    # === 新增：require_confirmation 拦截 ===
    request_confirm_token = hook_ctx.get("confirm_token") if isinstance(hook_ctx, dict) else None
    if tool.require_confirmation and not request_confirm_token:
        # 1. 调 pre-hook 链，可能有 ConfirmationGuardHook 拒绝
        hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
        if isinstance(hook_result, Reject):
            if hook_result.error_code == "confirmation_required":
                # 2. 工具"预演"：execute 一次但不落库，只返回 draft
                #    由工具内部识别 dry_run 参数或直接复用 execute
                draft_result = execute_guarded(
                    tool,
                    user_query,
                    context={**hook_ctx, "dry_run": True},
                )
                # 3. 工具若没返回 draft，兜底构造
                draft = draft_result.get("draft") if isinstance(draft_result, dict) else None
                if not draft:
                    return {
                        "answer": f"工具 {tool.name} 标记为需要确认，但未返回 draft，请联系管理员",
                        "intent": intent,
                        "tool_used": tool.name,
                        "tool_result": None,
                        "error": True,
                        "awaiting_confirmation": False,
                    }
                # 4. 存 token + draft
                token = str(uuid.uuid4())
                set_confirmation_draft(token, {
                    "tool_name": tool.name,
                    "user_query": user_query,
                    "context_sig": scope_sig,
                    "draft": draft,
                })
                # 5. 不走 LLM 合成，直接返回 awaiting_confirmation
                return {
                    "answer": draft.get("summary") or "请确认以下操作",
                    "intent": intent,
                    "tool_used": tool.name,
                    "tool_result": {"draft": draft},
                    "awaiting_confirmation": True,
                    "confirmation_token": token,
                    "error": False,
                }
        # 非 confirmation_required 的 Reject：交给上层处理（本计划不动）
    # === 拦截结束 ===

    # ... 既有 execute_guarded + 缓存 + LLM 合成逻辑 ...
```

**关键设计点**：

1. **预演机制**：用 `dry_run=True` 上下文标记让工具内部决定要不要真落库。默认行为是工具自己检查 `context.dry_run` 跳过副作用（如 schedule_tool 本来就无副作用，可忽略；swap 工具在 dry_run 下返回 draft 而不写库）
2. **不调 LLM 合成**：确认场景下 LLM 不知道"是否要执行"，强行合成反而误导用户
3. **`process_stream` 对称改动**：检测到 `tool.require_confirmation` 且无 confirm_token 时，yield `{"type": "awaiting_confirmation", ...}` 事件并 return

### 3.4 视图层 confirm replay

在 `SmartChatViewSet.create`（`views/chat.py:56-163`）起始处插入分支：

```python
def create(self, request):
    serializer = SmartChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    query = serializer.validated_data["query"]
    conversation_id = serializer.validated_data.get("conversation_id")
    confirm_token = request.data.get("confirm_token")  # 新增字段

    # === 新增：confirm replay 分支 ===
    if confirm_token:
        draft_entry = get_confirmation_draft(confirm_token)
        if not draft_entry:
            return Response(
                {"detail": "确认已过期或不存在，请重新发起", "code": "confirmation_expired"},
                status=status.HTTP_410_GONE,
            )
        # 校验 token 归属用户：draft_entry.context_sig 必须匹配当前 user
        expected_user_sig = f"u{request.user.pk}_"
        if not draft_entry.get("context_sig", "").startswith(expected_user_sig):
            return Response(
                {"detail": "该确认不属于当前用户", "code": "confirmation_user_mismatch"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # replay：跳过 pre-hook，直接 execute
        tool = ToolRegistry.get_tool(draft_entry["tool_name"])
        if not tool:
            return Response(
                {"detail": f"工具 {draft_entry['tool_name']} 未注册"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            tool_result = execute_guarded(
                tool,
                draft_entry["user_query"],
                context={"history": [], "confirmed": True, "confirm_token": confirm_token},
            )
            clear_confirmation_draft(confirm_token)
            # 直接返回工具结果给前端（不走 LLM 合成）
            return Response({
                "answer": tool_result.get("summary") or "操作已完成",
                "tool_used": tool.name,
                "tool_result": tool_result,
                "confirmed": True,
                "error": False,
            })
        except Exception as exc:
            logger.exception("confirm replay 执行失败: token=%s", confirm_token)
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # === replay 分支结束 ===

    # 既有编排路径...
```

**序列化器新增字段**：在 `SmartChatRequestSerializer` 加 `confirm_token = CharField(required=False, allow_blank=True)`。

### 3.5 输出契约

**场景 A：首次请求，工具需确认**
```http
POST /api/smart-assistant/chat/
{"query": "我想和李四换下周三的班"}
```
→ 200
```json
{
  "answer": "请确认以下换班申请",
  "intent": "swap_request_create",
  "tool_used": "swap_request_create",
  "tool_result": {"draft": {...}},
  "awaiting_confirmation": true,
  "confirmation_token": "uuid-v4",
  "error": false
}
```

**场景 B：用户确认，带 token 重发**
```http
POST /api/smart-assistant/chat/
{"query": "我想和李四换下周三的班", "confirm_token": "uuid-v4"}
```
→ 200
```json
{
  "answer": "换班申请已发起，申请号 #123",
  "tool_used": "swap_request_create",
  "tool_result": {...},
  "confirmed": true,
  "error": false
}
```

**场景 C：用户取消（前端不重发，自然过期）**
- 前端丢弃 token，draft 10 分钟后自动过期，无需后端处理

**场景 D：token 过期/不存在**
→ 410 Gone
```json
{"detail": "确认已过期或不存在，请重新发起", "code": "confirmation_expired"}
```

**场景 E：跨用户 token 重放**
→ 403 Forbidden

---

## 4. 实施步骤

> 每个步骤完成后跑 `pytest --ds=omni_desk_backend.settings.test` 与 `npm run lint`，再勾选。

### Phase A：基础函数

- [ ] **A.1**：`hooks/wiring.py` 新增 `apply_pre_execute_hooks`，复用 `_run_coroutine_sync` 模式
- [ ] **A.2**：`cache.py` 新增 `set/get/clear_confirmation_draft` 三个函数
- [ ] **A.3**：`tests/test_wiring_pre_execute.py` 覆盖：无 hook 快速路径 / hook 修改 params / hook 返回 Reject / 钩子异常降级
- [ ] **A.4**：`tests/test_cache_confirmation_draft.py` 覆盖：正常存取 / TTL 过期 / 跨 token 隔离 / clear 后再 get 返回 None
- [ ] **A.5**：`pytest -k wiring_pre_execute or cache_confirmation_draft` 绿

### Phase B：orchestrator 接入

- [ ] **B.1**：`agent/orchestrator.py` 的 `process()` 单工具路由段插入 confirm 拦截（§3.3 伪代码）
- [ ] **B.2**：`process_stream()` 对称改动：在 execute 前 yield `{"type": "awaiting_confirmation", ...}` 后 return
- [ ] **B.3**：`tests/test_orchestrator_confirm.py` 覆盖：
   - require_confirmation=True 工具 + 无 token → 返回 awaiting_confirmation（不调 LLM）
   - require_confirmation=True 工具 + 有 token → 跳过拦截，走既有路径（注：replay 路径实际由视图层拦截，此处只验证 orchestrator 不阻拦带 token 的请求）
   - require_confirmation=False 工具 → 不拦截
   - pre-hook 返回 Reject 但 error_code != confirmation_required → 走 fallback 错误返回

### Phase C：视图层 replay

- [ ] **C.1**：`serializers.py`（`SmartChatRequestSerializer`）加 `confirm_token` 字段
- [ ] **C.2**：`views/chat.py` 的 `SmartChatViewSet.create` 起始处插入 confirm replay 分支（§3.4）
- [ ] **C.3**：`tests/test_view_confirm_replay.py` 覆盖：
   - 有效 token + 工具存在 → 直接 execute，返回 confirmed=true
   - 无效 token → 410
   - 跨用户 token → 403
   - token 对应工具未注册 → 500
   - replay 期间工具抛异常 → 500 + log

### Phase D：端到端测试

- [ ] **D.1**：`tests/test_confirm_replay_e2e.py` mock 一个最小 ConfirmTool（risk=write, require_confirmation=True，execute 检测 dry_run 返回 draft / confirmed=True 时返回真实结果）
- [ ] **D.2**：覆盖 4 条端到端路径：
   1. create draft → return awaiting_confirmation
   2. confirm → replay → 真实 execute → 返回最终结果
   3. 用户取消 → token 过期 → 410
   4. 跨用户重放 → 403
- [ ] **D.3**：`pytest --ds=omni_desk_backend.settings.test -k confirm` 全绿，覆盖率 ≥ 80%

### Phase E：合并与回灌

- [ ] **E.1**：本地跑完整 `pytest` + `mypy`，无新警告
- [ ] **E.2**：建 PR `feat/sa-confirm-framework` → `main`，按 `feature-branch-workflow.md` 走 PR + CI
- [ ] **E.3**：CI 绿后合并，删除子分支
- [ ] **E.4**：回到 `feat/sa-swap-shift` 分支 rebase main，开始 Phase 1.1

---

## 5. 风险与依赖

### 5.1 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 工具未实现 dry_run 模式 | 中 | orchestrator 检测到 draft 为空时返回明确错误，提示工具需支持 dry_run |
| token 重放 | 中 | TTL 10 分钟 + 用户隔离（context_sig 前缀） + replay 成功后立即 clear |
| 视图层 replay 跳过 LLM 合成可能让用户觉得回答"机械" | 低 | 工具 execute 返回的 `summary` 字段作为 answer，工具作者可定制 |
| 既有 write 工具（如公告/项目工具）可能需要 confirm 但暂未声明 | 低 | 默认 `require_confirmation=False`，本次不强制要求所有 write 工具 |
| 流式路径（stream）与 confirm 流程冲突 | 中 | 本期跳过流式，仅 sync `create` 路径，文档明示 |
| 钩子链异常降级可能掩盖安全错误 | 低 | 与 `apply_post_execute_hooks` 同模式，已有约定 |

### 5.2 依赖

| 依赖 | 状态 |
|---|---|
| `Reject` 数据类 | ✅ 已有 |
| `HookRegistry.run_pre_hooks` | ✅ 已有 |
| `django.core.cache` | ✅ 已有（项目用 Redis 后端） |
| `ToolRegistry.get_tool` | ✅ 已有 |
| `SmartChatRequestSerializer` | ✅ 已有，需扩展 |

### 5.3 向后兼容

- `apply_pre_execute_hooks` 新增函数，不影响现有钩子调用
- orchestrator 拦截条件 `tool.require_confirmation and not confirm_token`：所有现有工具 `require_confirmation=False`，行为不变
- 视图层 confirm_token 为可选字段，缺省走既有路径
- 新增 PRE_EXECUTE 钩子（若有的话）默认不会自动注册，需手动 `register_builtin_hooks()` 扩展

---

## 6. 验收标准

- [ ] 单元测试全绿，覆盖率 ≥ 80%
- [ ] 端到端测试覆盖 4 条路径
- [ ] mock 一个 ConfirmTool，完整跑通 draft → confirm → replay
- [ ] 既有 13 个 read 工具行为完全不变
- [ ] 既有 cache / wiring 测试无回归
- [ ] `apply_pre_execute_hooks` 与 `apply_post_execute_hooks` 接口对称，易于扩展
- [ ] mypy 无新警告
- [ ] 文档：`docs/technical/...` 增"confirm-replay 框架"小节

---

## 7. 与上游分支的关系

本分支独立交付。完成后：

1. `feat/sa-confirm-framework` 合并到 `main`
2. `feat/sa-swap-shift` rebase `main` 后继续 Phase 1.1
3. swap 工具无需关心 confirm-replay 实现细节，只需声明 `require_confirmation=True` + 支持 `dry_run=True`

---

## 8. 决策日志

| 决策 | 选择 | 理由 |
|---|---|---|
| 框架补全范围 | 三处：wiring + orchestrator + view | 缺一不可；视图层无 replay 入口用户确认后无法真正落库 |
| 流式路径（stream）是否支持 confirm | ❌ 本期跳过 | 流式场景用户已看到 chunk 流，二次确认语义混乱；仅 sync 路径 |
| draft 存哪 | Django cache（Redis） | 短期、自动过期、跨请求隔离 |
| token TTL | 10 分钟 | 用户从看到弹窗到点确认通常 < 1 分钟；10 分钟足够容错 |
| dry_run 实现位置 | 工具内部识别 `context.dry_run` | 工具最清楚哪些步骤可预演哪些必须真做 |
| replay 时是否走 LLM 合成 | ❌ 不走 | 用户已确认，LLM 再合成属于画蛇添足；直接用工具 execute 返回的 summary |
| 既有 POST_EXECUTE 钩子是否复用 | ❌ 不复用 | 用途不同；若未来需要 audit 钩子拦截 confirm 流程，单独注册 |

---

## 9. 参考

- `omni_desk_backend/smart_assistant/hooks/base.py` 第 43–55 行：`Reject` 类
- `omni_desk_backend/smart_assistant/hooks/base.py` 第 273–305 行：`run_pre_hooks`
- `omni_desk_backend/smart_assistant/hooks/wiring.py` 第 125–141 行：`apply_post_execute_hooks` 模式
- `omni_desk_backend/smart_assistant/agent/orchestrator.py` 第 177–251 行：单工具路由段
- `omni_desk_backend/smart_assistant/views/chat.py` 第 56–163 行：SmartChatViewSet.create
- `omni_desk_backend/smart_assistant/cache.py` 第 84–94 行：`_key` 函数
- `docs/plans/2026-08-04_llm-swap-shift.md` §10：上游 swap 计划对子分支的依赖说明

# P1A-2 写工具速率限制 — 设计 spec

> 日期:2026-08-10
> 状态:✅ 已设计,待进入 plan + 实施
> 上游方案: `docs/plans/2026-08-09_ai-midplatform-digital-employee-optimization.md` §3 P1-A (原存档于 PR #183 分支,后合入 main,文件已移除时保留本文)
> 关联 commit: 4c0d8e3a (P1A-1 收口)、5e8728df (chore 顺手修)
> 关联代码:
> - `omni_desk_backend/smart_assistant/middleware/rate_limit.py` — chat 限流(可参照实现)
> - `omni_desk_backend/smart_assistant/hooks/builtin/confirmation.py` — 拦截点形态参考
> - `omni_desk_backend/smart_assistant/tools/base.py` — `require_confirmation` 标记

---

## 一、背景与目标

### 1.1 背景

总方案 §3 P1-A 路线中,P1A-1 已完成「LLM 调用统一收口到 LLMRouter」(`file_processing` + `office_assistant`),`PR #189` 合入。下一步 P1A-2 是「写工具速率限制」:

> llm-swap-shift Phase 5 遗留:写工具单独限流(如 10/min),区别于 chat 全局 30/min
> 涉及文件: `smart_assistant/middleware/rate_limit.py`

现况缺口:
- `smart_assistant/middleware/rate_limit.py` 仅拦 `/api/smart-assistant/chat/` 路径,对**写工具调用**无任何 DoS 防护
- 用户可在 1 分钟内用同一身份发起任意多次写工具(swap / 公告 / 备忘录 / …)的"准备动作",触发大量短 TTL 缓存、覆盖式 draft、coroutine 占用、审计日志膨胀
- 总方案明文要求"写工具单独限流,区别于 chat 全局"

### 1.2 目标

把写工具的速率限制作为中台基建的**最后一块**:
- 单一计数器 = 用户级(`user_id`),对所有 `require_confirmation=True` 工具合计计数
- 触发位置 = 与 ConfirmationHook 同源的 pre_execute 钩子链
- 超限语义 = 与 ConfirmationHook 同款的 `Reject(error_code="rate_limit_exceeded")` 硬拒
- 复用既有基础设施 = Django cache(Redis prod / LocMemCache dev/test)、fixed window、不引入新依赖

### 1.3 非目标(YAGNI)

- 不做 per-tool 细粒度限制(等 P1A-6 工具注册中心雏形时再加)
- 不接 LlmAppConfig DB 调谐阈值(env var 单一入口,避免多机配置不同步)
- 不切换滑动窗口或 token bucket(fixed window 在 chat 中间件已用,一致性优先)
- 不做 admin 豁免(任何人统一 1 个用户额度,跟 chat 一致)
- 不替代 ConfirmationHook — 两个 hook 职责独立:Confirmation = 二次确认,RateLimit = 频次控制

---

## 二、技术方案

### 2.1 架构总览

```
用户发起任意聊天请求(含写意图)
  │
  ▼
AgentOrchestrator.process_query()
  │  解析 → 选出 tool(require_confirmation=True)
  ▼
apply_pre_execute_hooks(tool, ctx, params)
  │   (在 wiring.py 中注册链: RateLimitHook → ConfirmationHook → ...)
  ▼
RateLimitHook.pre_execute(tool, ctx, params)
  │  - tool.require_confirmation == False → return params (放行,Read 工具不计)
  │  - tool.require_confirmation == True  → 调用 check_write_rate_limit(ctx.user.id)
  │       - allow=False → Reject(error_code="rate_limit_exceeded", retry_after=ttl)
  │       - allow=True  → cache.incr(user_id_key) → return params
  ▼
ConfirmationHook.pre_execute(tool, ctx, params)   [既有行为]
  │  - require_confirmation=True → Reject(confirmation_required) → draft / awaiting
  │  - require_confirmation=False → return params
  ▼
Orchestrator 收到任一 Reject → 不走 LLM 合成 → 直接返回错误响应给前端
  │
  ▼
前端:看到 error_code / retry_after,显示文案 + 退避提示
```

Replay 路径(`POST /api/smart-assistant/chat/` 带 `confirm_token`)位于 `smart_assistant/views/chat.py:create()`:**直接调用 `execute_guarded(...)`**、**不重跑 `apply_pre_execute_hooks`**——本 spec 因此不需要在视图层加重复检查。

### 2.2 文件改动

| 文件 | 类型 | 改动 |
|---|---|---|
| `omni_desk_backend/smart_assistant/middleware/rate_limit.py` | 改 | 新增 `SMART_ASSISTANT_WRITE_RATE_LIMIT` 常量(env var 默认 10) + `check_write_rate_limit(user_id)` 函数(复用现有 fixed window 算法 + cache.incr 回落逻辑) |
| `omni_desk_backend/smart_assistant/hooks/builtin/rate_limit.py` | 新 | 类 `RateLimitHook`,`name="write_rate_limit"`,`async pre_execute(tool, ctx, params)` |
| `omni_desk_backend/smart_assistant/hooks/builtin/__init__.py` | 改 | 导出 `RateLimitHook`,更新顶部 docstring "规划中" 段去掉 |
| `omni_desk_backend/smart_assistant/hooks/wiring.py` | 改 | 在生产注册位(`get_registry()` 调用集中位置)新增 `RateLimitHook`,保证 PRE_EXECUTE 链包含 |
| `omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py` | 新 | 6 个测试覆盖 hook 单测 + 集成 + replay 不双计 |
| `docs/technical/16-smart-assistant.md`(或新建第 42 章) | 改/新 | 接入文档:hook 职责 + 配置项 + cache key 命名空间 + 测试指引 |

### 2.3 配置

```python
# omni_desk_backend/smart_assistant/middleware/rate_limit.py 中新增
SMART_ASSISTANT_WRITE_RATE_LIMIT = int(
    os.environ.get("SMART_ASSISTANT_WRITE_RATE_LIMIT", "10")
)
WRITE_RATE_WINDOW = 60  # 秒,1 分钟
WRITE_RATE_NAMESPACE = "smart_assistant:write_rate_limit"
```

部署侧:
- 生产 `production.py` / `base.py` 内已有 `SMART_ASSISTANT_CHAT_RATE_LIMIT` 模式,按同样模板追加 `SMART_ASSISTANT_WRITE_RATE_LIMIT` 默认值到 docstring / `.env.example`(若有)
- **不接 LlmAppConfig DB 调谐**

### 2.4 Cache Key & 算法

复用 chat 中间件同一套,无新机制:

```python
def check_write_rate_limit(user_id: int) -> tuple[bool, int, int]:
    """
    Returns:
        (allowed, remaining, retry_after)
    """
    key = f"{WRITE_RATE_NAMESPACE}:{user_id}"
    current = cache.get(key, 0)

    if current >= SMART_ASSISTANT_WRITE_RATE_LIMIT:
        try:
            ttl = cache.ttl(key) or WRITE_RATE_WINDOW
        except (AttributeError, NotImplementedError):
            ttl = WRITE_RATE_WINDOW
        return False, 0, ttl

    # Django locmem cache.incr 在 key 不存在时抛 ValueError;先 set 再 incr 兼容两类 backend
    try:
        new_value = cache.incr(key)
    except ValueError:
        cache.set(key, 1, WRITE_RATE_WINDOW)
        new_value = 1
    else:
        cache.set(key, new_value, WRITE_RATE_WINDOW)

    remaining = SMART_ASSISTANT_WRITE_RATE_LIMIT - new_value
    return True, max(remaining, 0), 0
```

Cache backend 行为:开发 / 测试用 LocMemCache,生产 Redis——与 chat 限流完全对齐,运维无需新增缓存后端。

---

## 三、组件契约

### 3.1 `RateLimitHook` 类

```python
class RateLimitHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 工具做频次控制。"""

    name = "write_rate_limit"

    async def pre_execute(self, tool: Any, ctx: Any, params: dict) -> dict | Reject:
        # read 工具直接放行,不计数
        if not getattr(tool, "require_confirmation", False):
            return params

        # ctx 为 ToolContext / SharedContext / dict,统一约定有 .user 或 ["user"] 字段
        user = _extract_user(ctx)
        if user is None or not getattr(user, "is_authenticated", False):
            return params  # 未认证直接放行(上层 ChatMiddleware 兜底)

        allowed, remaining, retry_after = check_write_rate_limit(user.id)
        if not allowed:
            return Reject(
                reason=(
                    f"写工具调用过于频繁,请 {retry_after} 秒后再试。"
                    f"当前每用户每分钟上限 {SMART_ASSISTANT_WRITE_RATE_LIMIT} 次"
                ),
                error_code="rate_limit_exceeded",
                retry_after=retry_after,
            )
        return params
```

`_extract_user` 工具函数(同模块内 helper):支持 `ToolContext.user` / `ctx["user"]` / `request.user` 三种形态,与 ConfirmationHook 既有 `_extract_user` 实现保持一致(若有),无则新增同名 helper。

### 3.2 Pre-execute 注册链

按 `smart_assistant/hooks/wiring.py` 现有约定(wiring 文件统一登记注册),在原 `ConfirmationHook` 注册点附近加入 `RateLimitHook`。具体顺序:
- **生产注册顺序**: `RateLimitHook` 排在 `ConfirmationHook` **之前**(亦即先过频次再过确认)。理由:用户被限流不应再触发任何 draft 缓存,省一次 Redis 写
- 注册失败策略:同 `_run_coroutine_sync` 内部吞错降级;不会因注册缺位导致主流程断

### 3.3 错误响应契约(前端契约)

Orchestrator 收到 `Reject(error_code="rate_limit_exceeded")` → 透传给视图层 (`views/chat.py` 既有的 `_resolve_error` / 错误响应路径):

```json
{
  "answer": "写工具调用过于频繁,请 47 秒后再试。当前每用户每分钟上限 10 次",
  "intent": "<意图>",
  "tool_used": "<tool_name>",
  "tool_result": null,
  "error": true,
  "error_code": "rate_limit_exceeded",
  "retry_after": 47
}
```

- 视图层透传:在 `views/chat.py:create()` 与 `stream()` 的既有错误响应分支加 `error_code` / `retry_after` 字段(向后兼容,字段缺省时前端按通用错误展示)
- 前端:复用既有错误 toast / display;对 `error_code === "rate_limit_exceeded"` 渲染文案"操作过于频繁,请 X 秒后再试"
- SSE 流路径(`process_stream`):同理在事件载荷上加字段,前端按事件处理
- 失败兜底:`rate_limit_exceeded` 字段解析失败 → 退化为通用错误,功能可用性不降

### 3.4 可观测性

- `RateLimitHook.pre_execute` 超限时:`logger.warning("写工具限流拦截: user_id=%d, retry_after=%d", ...)`
- 视图层透传错误码,可被 `stats/stats.py` 聚合到错误类型分布
- `doctor.py` 的 `cache_rate_limit` 检查项(`/api/smart-assistant/doctor/`)扩展加一项 `cache_write_rate_limit`,复用同一 `cache` 实例校验

---

## 四、实施步骤(高层)

> 详细步骤拆分在 `superpowers:writing-plans` 输出的 plan 文档中(下一步动作)。

1. **新增 `check_write_rate_limit` helper** 在 `middleware/rate_limit.py`,确保与 `check_rate_limit` 一致的算法与 fallback
2. **新增 `RateLimitHook` 类** 在 `hooks/builtin/rate_limit.py`(新文件)
3. **导出 + 接线** 在 `hooks/builtin/__init__.py` + `hooks/wiring.py` 登记注册
4. **单元 / 集成测试** 在 `tests/test_rate_limit_hook.py`(6 用例) + 既有 `test_orchestrator_confirm.py` 追加 1 用例验证 hook 协同
5. **本地 + CI 验证**:locmem 模式跑 `pytest smart_assistant/tests/test_rate_limit_hook.py smart_assistant/tests/test_orchestrator_confirm.py` + 全仓 `pytest --ds=settings.test`
6. **文档**:在 `docs/technical/` 智能助手章节末尾追加 hook 列表变更项;若空间不够新建 `42-write-tool-rate-limit.md` 章节
7. **顺手修**:若 `_extract_user` helper 缺失,合并到 confirmation.py 现成实现或新写一个共用

---

## 五、测试策略

| ID | 类型 | 路径 | 覆盖 |
|---|---|---|---|
| T1 | 单测 | `test_rate_limit_hook.py::test_write_tool_increments_counter` | pre_execute 一次后 cache.incr +1 |
| T2 | 单测 | `test_rate_limit_hook.py::test_read_tool_bypasses` | `require_confirmation=False` 不计数,cache key 不存在 |
| T3 | 单测 | `test_rate_limit_hook.py::test_limit_exceeded_returns_reject` | 第 N+1 次返回 Reject(error_code="rate_limit_exceeded", retry_after>0) |
| T4 | 单测 | `test_rate_limit_hook.py::test_different_users_independent` | user A 满,user B 不受影响 |
| T5 | 单测 | `test_rate_limit_hook.py::test_anonymous_passthrough` | 匿名 ctx 直接放行(由 ChatMiddleware 兜底) |
| T6 | 集成 | `test_rate_limit_hook.py::test_orchestrator_returns_rate_limit_error` | 走 `AgentOrchestrator.process_query` 到错误响应,error_code 命中 |
| T7 | 回归 | `test_orchestrator_confirm.py::test_rate_limit_does_not_disturb_normal_confirm` | 既有 confirm-replay 测试套不被新增 hook 干扰 |

**测试基础设施**:
- LocMemCache 默认;`cache.clear()` 在 `setup_method` 中清理
- `RequestFactory` + `_FakeResponse`(沿用 `test_middleware_chain_coverage.py` 模式)
- 用户 fixture 复用 `admin_user_obj`(conftest 中既有)
- mock_llm_router / mock_tool_registry fixture 复用

**覆盖率目标**:P1A-2 新代码 ≥ 90%(小函数明确,容易测全)。

---

## 六、风险评估与依赖

### 6.1 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **Count 与 confirm 流程串味**: hook 添加后,既有 confirm-replay 测试可能因 wire 注册顺序而 flake | 中 | T7 跑既有 confirm 测试套确保不退步;wire 注册集中化,顺序明确 |
| **多 Agent fan-out 写工具调用风暴**: 主 agent 派发的 sub-agent 调用写工具时复用同 user 计数(预期行为,但若 sub-agent 数量大可能瞬间打满) | 低 | YAGNI 不细分;同一 hook 兜住;若出现再升级 |
| **生产部署 cache flush 后短期内计数错乱**: Redis 重启清空计数器 | 低 | 与 chat 限流同源,运维已知;可接受 |
| **Audit 误增**: pre_execute 失败多走一次 warning log,审计日志增长 | 低 | logger.warning 即可,AgentLog AuditLogHook 已统一采集 |

### 6.2 依赖

- Django cache(Redis / LocMem)——既有
- ConfirmationHook / apply_pre_execute_hooks——既有,不破坏契约
- ToolContext / SharedContext 形态——既有,`_extract_user` helper 复用已有或新加(见下)
- `smart_assistant/hooks/wiring.py` 注册入口——既有,集中添加

### 6.3 未知点 / 后续可能

- 是否加 per-tool override 字段?留 P1A-6 时一起做
- 是否将失败计数也累加(用户连续被拒也扣额度)?当前实现是只有 allow 才 incr,被拒不扣;这是有意为之
- `confirm-replay` 用户在窗口末期利用的边界 race?由 TTL 自动清,可接受

---

## 七、不在范围内

- 数字员工(P1B-2)的主动巡检写操作的限额(spec 没纳入,走同 hook 自动覆盖)
- Sliding window / token bucket 算法
- Per-tool / per-category 维度限额
- 多 Agent fan-out 独立计数器
- LlmAppConfig DB 配置项
- 前端 UI 改版范围(只加字符串分支)

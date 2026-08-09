# L1.1 原生 Function Calling 加固 — 设计文档

> 📅 **日期**:2026-08-09
> **作者**:AI 中台规划(L1 final review 遗留项 + streaming 目标行为)
> **状态**:✅ 已实施(2026-08-09)
> **优先级**:P0(L1 遗留 3 子项:流式 / 结构化参数 / 确认 hook)
> **预计工时**:1-1.5 周

## 1. 目标与背景

### 1.1 现状

L1(L1 原生 Function Calling,merge commit `486708ab`)已交付:

- 19 个 BaseTool 实现 `get_openai_tool_schema()`(OpenAI strict JSON Schema)
- `LLMRouter.generate_with_tools()`(非流式三元组)+ `AgentOrchestrator._process_tool_calls_path()` 原生主循环(最多 3 轮)
- JSON fallback 路径保留作 A/B;scope-aware 执行 + 完整 hook 链(C-1/C-2 已修)
- `AgentLog.tool_calls_meta` 决策日志;staff 灰度开关 `USE_NATIVE_TOOL_CALLS_FOR_ALL`

**关键文件**:`omni_desk_backend/smart_assistant/agent/orchestrator.py`、`smart_assistant/tools/*`、`smart_assistant/hooks/wiring.py`、`smart_assistant/views/chat.py`

### 1.2 遗留缺口(来自 L1 final review)

| 编号 | 缺口 | 影响 |
|---|---|---|
| **F2** | `process_stream()` 不走原生 tool_calls | SSE 路径工具决策仍靠 intent 分类,无 LLM 自主 tool_calls |
| **I-2** | `_dict_to_query()` 只取 `query`,丢弃结构化字段 | LLM 拆日期查错(schedule)、永远读第 0 片(office_read)、部门过滤失效(personnel) |
| **I-1** | 无 PRE_EXECUTE hook 产生 `Reject(confirmation_required)` | `require_confirmation=True` 写工具(office_generate/swap×2)无确认直接执行,**fail-open** |

### 1.3 目标

- **F2**:`process_stream()` 支持原生 tool_calls —— 缓冲首轮 + 流式最终轮,完全委托原生路径(与 `process()` 行为一致)。
- **I-2**:原生路径把 LLM 提供的完整结构化参数透传给工具,工具显式消费;缺失时回退现有 query 解析。
- **I-1**:新增并注册 ConfirmationHook(PRE_EXECUTE),激活写工具 confirm-replay,变 **fail-closed**。

### 1.4 范围

**包含 ✅**

- F2:`process_stream()` 原生分支 + 工具轮复用 + 流式最终轮 + confirm-replay 透传 + 降级
- I-2:`_execute_native_tool()` 透传完整 validated dict + 受影响工具消费结构化字段
- I-1:`ConfirmationHook` + `register_builtin_hooks()` 注册 + confirm-replay E2E 测试
- 全量回归(后端 2290+ / 前端 509)+ 灰度开关语义不变

**不包含 ❌**

- `generate_with_tools()` 加 `stream=True`(首轮缓冲,无需 delta 解析;YAGNI)
- Anthropic tool_use / Gemini function_calling 差异化适配(另行立项)
- aggregated_day 链式调用迁入原生路径(保持 JSON/非原生路径)
- 其余工具的全部结构化字段逐一消费(I-2 分两层,见 §4.3)

### 1.5 约束

- Python 3.10 / Django 4.2 / PostgreSQL(`CLAUDE.md`)
- 内网离线部署,无外网依赖
- 现有 hook 注册表 / confirm-replay 视图层 / 前端 `awaiting_confirmation` 均**复用不重写**
- 中文为主

## 2. 整体架构

三个子项独立可交付,但共享原生 tool_calls 代码区,合并为一次 spec → plan → SDD 实施:

```
┌─ AgentOrchestrator ────────────────────────────────────────────────┐
│  process() (非流式)                    process_stream() (SSE)       │
│   ├─ 门控: USE_NATIVE + endpoint 能力 + staff   ├─ 同左(新增)        │
│   ├─ _process_tool_calls_path (原生主循环)      ├─ F2: 原生流式分支   │
│   │    ├─ 工具轮 (复用)  ◄── I-2 透传参数        │    ├─ 缓冲工具轮    │
│   │    └─ 最终轮 (非流式)                       │    └─ 流式最终轮    │
│   └─ _process_json_path (JSON fallback)         └─ intent 路由(不变)  │
│                                                    ↑ 原生分支失败降级  │
└──────────────┬──────────────────────────────────────┴────────────────┘
               │ tool.execute_guarded(params=validated, ...)
               ▼
┌─ Tools ────────────────┐   ┌─ Hooks ─────────────────────────────┐
│ BaseTool 19 个          │   │ PRE_EXECUTE: ConfirmationHook (I-1) │
│ 消费 params 结构化字段   │   │ POST_EXECUTE: PiiMasking            │
│ (I-2)                   │   │ ON_FAILURE: TimeoutGuard            │
└─────────────────────────┘   └──────────────────────────────────────┘
```

**实施顺序**(依赖驱动):

1. **I-1**(ConfirmationHook)— 独立小改动,关闭安全缺口
2. **I-2**(结构化参数透传)— 独立,复用工具轮
3. **F2**(流式原生)— 最复杂,复用前两者

## 3. F2 设计(process_stream 原生 tool_calls)

### 3.1 门控(与 `process()` 对称)

```python
use_native = (
    bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
    and self._endpoint_supports_tool_calls()
    and (
        user_is_staff   # tool_context.user.is_staff
        or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False))
    )
)
```

- `process_stream()` 入口新增同一段门控;`use_native=True` 走原生流式分支
- 无用户上下文(内部调用)按非 staff 处理 → 走现有 intent 路由
- 原生分支异常 → 降级到现有 intent 流程(不抛给视图层)

### 3.2 原生流式路径流程

```
1. 缓存短路(保留现有,缓存键 tool_call_path="none")
2. 首轮(缓冲): router.generate_with_tools(messages, tools, tool_choice="auto")
   ├─ 无 tool_calls → 输出即最终答案:直接以单 chunk 输出缓冲 content,
   │    不额外调 LLM(原生路径跳过 intent,无 generate_answer_stream)
   └─ 有 tool_calls → 进入工具轮
3. 工具轮(复用 _process_tool_calls_path 机制,最多 3 轮):
   - 每轮: 解析/校验 → _execute_native_tool(scope-aware + 完整 hook 链
     + confirm-replay + I-2 透传)→ 结果 append 回 llm_messages
   - 3 轮后强制 tool_choice="none"
4. 最终轮(流式,仅当工具轮实际执行过): router.generate(
     messages=final_messages, stream=True)
   → 逐 chunk yield sse_event({"type": "chunk", "content": chunk})
   (首轮即无 tool_calls 的 case 走步骤 2 直出,不进入此步,避免无谓重生成)
5. 全程 yield meta/chunk/done 事件,契约与现有流式一致:
   - meta: intent/tool_used/tool_result/sources
   - done: finish_reason="stop", error=is_failed_answer(full_answer)
6. 写 AgentLog(tool_call_path="native", tool_calls_meta, tool_calls_rounds)
```

**要点**:

- **工具轮与最终轮解耦**:为复用,把工具轮从 `_process_tool_calls_path` 抽出为
  `_run_tool_calls_rounds(query, context, llm_messages) -> (final_messages, usage, meta)`;
  `process()` 在其后做一次非流式最终轮,`process_stream()` 在其后做流式最终轮。
  两路径对称,`process()` 现有行为 100% 不变。
- **最终轮真流式**:工具轮结束后用 `router.generate(messages=final_messages, stream=True)`
  重新生成最终答案,用户看到"打字中短暂停顿后出最终答案"(spec §6.3)。代价:工具轮
  结束后多一次最终轮 LLM 调用(约等于最终轮自身成本),换取真实打字动画。**仅当工具轮
  实际执行过才重生成**;首轮即无 tool_calls 的 case 直接输出缓冲 content,零额外成本。
- **confirm-replay 透传**:流式路径写工具(经 I-1 激活)命中
  `Reject(confirmation_required)` → dry_run → draft → yield
  `awaiting_confirmation + confirmation_token` 事件 → 前端确认后 replay 视图执行。
  (现有 `process_stream` 已具 confirm-replay 拦截骨架,原生分支复用同逻辑。)
- **跳过 intent 路由**:原生开启时跳过 `classify_intent` + 单工具路由 +
  `tool_chain` 检测(用户已确认"完全委托原生路径")。

### 3.3 与现有路径的关系

| 现有机制 | 原生流式路径 | JSON/intent 路径 |
|---|---|---|
| 回答缓存 | 保留(缓存键 `tool_call_path="none"`) | 保留 |
| `classify_intent` 单工具路由 | **跳过**(LLM 自主决策) | 保留 |
| `generate_tool_chain_plan` / `_process_chain` | **跳过** | 保留(aggregated_day 卡片) |
| confirm-replay | ✅(经 ConfirmationHook + 现有拦截) | ✅ |
| scope-aware + hook 链 | ✅(复用 `_execute_native_tool`) | ✅ |
| 端点降级 | ✅(`generate_with_tools` 异常 → intent 流程) | ✅ |

## 4. I-2 设计(结构化字段透传)

### 4.1 根因

`_execute_native_tool()`(`orchestrator.py:595`)先 `_dict_to_query(validated)` 只取
`query`,再 `params={"query": query}` 传给工具 → LLM 提供的结构化字段
(date_from / chunk_index / department / limit / status / …)全部丢失。

### 4.2 修复机制(一处改动)

```python
# _execute_native_tool 内
query = _dict_to_query(validated)     # 保留:确认/审计/日志/回退用
params = validated                     # 改为透传完整字典
# scope 工具:
execute_guarded(tool, params=params, scope=..., qs=..., context=context)
# 非 scope 工具:
execute_guarded(tool, query=query, params=params, context=context)
```

- `query` 仍是自然语言主输入(不把结构化字段拼接进 query,保留 F1 防污染决策)
- 结构化字段经 `params` 字典显式传递,工具 opt-in 读取
- 兼容:JSON fallback 路径(`_legacy_process`)不动;scope 工具
  `execute(params, scope, qs)` 签名已具备 `params` 参数(C-1 扩展)

### 4.3 工具消费分层

**Tier 1(首批,缺字段即查错/丢语义,必改)**:

| 工具 | 消费字段 | 修复效果 |
|---|---|---|
| `schedule_query` | `date_from`/`date_to`/`personnel_name` | LLM 拆日期后按范围过滤 |
| `office_read` | `chunk_index` | 按 LLM 指定切片读取 |
| `personnel_query` | `department`/`status` | 部门/在职状态过滤 |
| `memo_query` | `is_completed` | 完成状态过滤 |
| `news_query`/`document_query`/`announcement_query` | `limit` | 条数上限 |
| `event_query`/`meeting_room_query` | `target_date` | 目标日期过滤 |

**Tier 2(其余工具,字段存在但缺失时行为仍合理,可后续追)**:
compliance(severity/due_within_days)、external_link(category)、project(manager/status)、
sensor(category/status)、rag(top_k/dataset_ids)、spreadsheet(sheet_name)、
office_generate(structure_hint)、swap_query(action/swap_id/…)。

**回退语义**:结构化字段缺失 → 工具保持现有 query 解析/默认行为,零回归。

## 5. I-1 设计(生产确认 ConfirmationHook)

### 5.1 缺口确认

- 写工具 `require_confirmation=True`:office_generate / swap_create / swap_decide
- 前端确认重放链已完备:awaiting_confirmation → confirm_token → replay 视图(`chat.py:134`)
- **缺失**:无任何 PRE_EXECUTE hook 产生 `Reject(confirmation_required)`(全库仅
  `wiring.py:171` docstring 提及)→ `apply_pre_execute_hooks` 快速路径直接放行
  (`wiring.py:189` 无 pre-hook 时返回 params)→ 写工具无确认直接执行,**fail-open**

### 5.2 设计

```python
# smart_assistant/hooks/builtin/confirmation.py (新增)
class ConfirmationHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 的工具返回 Reject(confirmation_required),
    激活 orchestrator 的 confirm-replay 拦截(写工具 fail-closed)。"""

    name = "confirmation"

    async def pre_execute(self, tool, ctx, params):
        if getattr(tool, "require_confirmation", False):
            return Reject(
                reason=f"工具 {getattr(tool, 'name', '')} 需要用户二次确认",
                error_code="confirmation_required",  # orchestrator 据此触发 confirm-replay
            )
        return params  # 非写工具放行
```

### 5.3 注册(生产装配点 `register_builtin_hooks`)

`apps.ready()` → `hooks/wiring.py:register_builtin_hooks()` 是**唯一生产 hook 装配点**
(现已注册 PiiMaskingHook → POST_EXECUTE + TimeoutGuardHook → ON_FAILURE;
`get_registry()` 本身创建空注册表)。把 ConfirmationHook 加入同一函数:

```python
# hooks/wiring.py register_builtin_hooks()
reg.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)  # 高优先级
```

- **幂等**:`register_builtin_hooks` 已按 hook name 去重,`ready()` 多次调用不重复挂载
- **测试隔离**:`get_registry(reset=True)` 得空注册表;confirm-replay 测试需显式
  调用 `register_builtin_hooks()` 或单独注册 ConfirmationHook(plan 细化)
- **不误伤**:read 工具 `require_confirmation=False` → 放行,现有测试不受影响

**激活链路**(写工具 fail-open → fail-closed):ConfirmationHook 返回
`Reject(confirmation_required)` → `_execute_native_tool` / `process_stream` 现有
`if isinstance(hook_result, Reject) and error_code == "confirmation_required"` 分支
被激活 → dry_run 取 draft → `set_confirmation_draft` 存 token → 返回
awaiting_confirmation + confirmation_token → 前端二次确认 → replay 视图
(`chat.py:134`)执行工具 → 清理 draft。审计经现有 AuditLogHook 记录。

## 6. 测试策略

### 6.1 单元测试

| 测试 | 断言 |
|---|---|
| `test_confirmation_hook_blocks_write_tools` | write 工具 → Reject(confirmation_required);read 工具放行 |
| `test_schedule_date_range_passthrough` | validated 含 date_from/date_to → schedule 按范围过滤 |
| `test_office_read_chunk_index` | validated 含 chunk_index=2 → 返回第 3 片 |
| `test_personnel_department` | validated 含 department → 过滤生效 |
| `test_no_structured_fields_fallback` | 无结构化字段 → 回退 query 解析(回归) |

### 6.2 集成 / E2E 测试

| 测试 | 场景 |
|---|---|
| `test_confirm_replay_e2e` | 写工具触发确认 → draft → replay 视图执行成功 → PII 脱敏生效(防 C-2 回归) |
| `test_streaming_native_path_tool_calls` | 原生开启 → 首轮 tool_calls → 工具执行 → 流式最终答案 |
| `test_streaming_native_path_no_tools` | 首轮无 tool_calls → 直接流式 content |
| `test_streaming_fallback_json` | 端点无能力 / 开关关 → 走现有 intent 路由(回归) |
| `test_streaming_confirm_replay` | 流式写工具 → awaiting_confirmation 事件透传 |

### 6.3 回归

- 后端全量(pytest --ds=…test)+ 前端全量(npm test),0 fail
- `USE_NATIVE_TOOL_CALLS_FOR_ALL=True` 灰度语义不变

## 7. 错误处理

| 失败场景 | 行为 | 用户感知 |
|---|---|---|
| 端点不支持 tool_calls / 开关关 | 原生分支不进入 → intent 流程 | 无感知 |
| 原生分支异常 | 降级到现有 intent 流程(与 process() 对称) | 无感知 |
| 工具轮 3 轮后 LLM 仍调工具 | 强制 tool_choice="none" | LLM 给基于已有结果的回答 |
| 最终流式轮失败 | 流式错误文案 + kind/hint(与现有流式一致) | 失败回答 + kind/hint |
| 写工具无确认触发 | 不执行(ConfirmationHook Reject) | awaiting_confirmation 事件 |

## 8. 风险与边界

| 风险 | 缓解 |
|---|---|
| I-2 改动面大(17 工具 schema 有结构化字段) | 机制一处 + Tier 1 首批;Tier 2 后续,缺失即现行为 |
| I-1 可能误伤现有测试(全局注册表) | ConfirmationHook 仅对 `require_confirmation=True` 生效;注册表隔离可测 |
| F2 与 tool_chain / aggregated_day 冲突 | 原生开启跳过 `_process_chain`;aggregated_day 走非原生路径,不回退 |
| 最终轮重生成多一次 LLM 调用 | 换取真实打字动画;工具轮已缓冲,增量成本≈最终轮自身 |
| 缓存键语义 | 原生流式沿用 `tool_call_path="none"` 短路,不污染 legacy |

**明确不做(YAGNI)**:`generate_with_tools(stream=True)`、Anthropic/Gemini 适配、
aggregated_day 迁入原生、Tier 2 全部字段一次性消费。

## 9. 回滚与灰度

- 每子项独立可回滚:I-1(hook 反注册)、I-2(params 改回 `{"query": query}`)、
  F2(门控关闭走 intent 流程)
- `USE_NATIVE_TOOL_CALLS_FOR_ALL` 灰度不变;F2 默认仅 staff,与 L1 一致

## 10. 相关文档

- L1 设计:`docs/superpowers/specs/2026-08-06-native-function-calling-design.md`
- L1 实施:`docs/superpowers/plans/2026-08-06-native-function-calling.md`
- L1 final review / fix wave:`.superpowers/sdd/2026-08-06-native-function-calling/`
- 本文档的 spec 自检 + 用户审阅通过后,调用 writing-plans 进入实施计划

## 11. 实施记录(2026-08-09)

> L1.1 加固已按本 spec 落地(6 个 Task 全部完成)。以下为实施中与 spec 原文的偏离点,便于追溯。

1. **F2**:`_process_stream_tool_calls_path` 非确认场景补充先发 meta 事件(否则破坏既有 SSE 契约 `types[0]=="meta"`,前端依赖首个事件为 meta 渲染意图/工具)。spec §3.2 步骤 5 未显式要求首帧 meta,实现按现有流式契约补足,与 confirm-replay 分支的 meta(`intent="tool_call"`)保持一致;JSON 降级时透传其 intent 供前端展示。
2. **I-2**:personnel `status` 模型存 code(`active`/`inactive`),而 LLM schema 暴露的是中文枚举(在职/离职)。实现加"中文 label → code"映射回退(`label_to_code = {label: code for code, label in Personnel.STATUS_CHOICES}`),否则中文值直接过滤查不到任何记录。spec §4.3 Tier 1 表未提此映射细节。
3. **I-2**:event / meeting_room 的 `target_date` 按各自实际模型驱动 —— `event_query` 用 `duty_date` 过滤(Schedule 模型),`meeting_room_query` 用预订窗口计算可用性(Booking 模型),而非统一按 spec 的"目标日期过滤"表述。同时修复了此前结构化 `target_date` 被 `_dict_to_query` 捕获但从未生效的 bug(L1 遗留,spec 未单列)。
4. **I-1**:ConfirmationHook 全局注册后,MagicMock 工具测试(`test_hooks_wiring` / `test_orchestrator` / `test_hooks_builtin`)中 `require_confirmation` 隐式恒真 → mock 工具显式补 `require_confirmation=False` 适配;`test_hooks_builtin` 的 builtin 导出断言纳入新钩子。这是对 spec §5.3"注册表隔离可测"的落地细节补充。
5. **附**:全量回归通过 —— 后端 2307 passed / 0 failed(coverage 91.76%,≥80%),前端 509 passed / 0 failed(首轮全量跑曾出现 1 例 timing-flaky 的 `SmartChatPage.feedback` waitFor 超时,该测试与本分支无关且隔离重跑通过;复查全量 0 failed)。

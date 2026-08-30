# 智能助手真实多智能体编排 — 设计文档

**日期**：2026-08-30
**状态**：待评审
**分支**：`feat/smart-assistant-real-orchestration`

## 1. 背景与目标

### 1.1 现状

`docs/technical/43-smart-assistant-collab-card.md` 描述的多智能体协作卡片是**纯前端剧本回放**：`useScenarioPlayer` 用 `setTimeout` 按预置 `steps` 数组推进，`useSmartChat` 命中关键词时注入 `collab_card` 并跳过后端调用。8 个剧本全部是硬编码的假事件序列。

后端的多智能体设施**已存在但未接通**：

- `AgentTask` / `AgentSubTask` / `AgentEvent` 三张表齐备，`AgentEvent.EVENT_TYPE_CHOICES` 已预留 `subtask.progress` / `subtask.tool_call` / `subtask.quality_gate` / `supervisor.decision` / `hook.triggered`
- `Supervisor.generate_task_packet()` 真实调用 LLM 生成任务分解
- `MultiAgentExecutor` / `PipelineRunner` / `SubTaskRunner` / `CheckpointManager` 完整实现 Pipeline 模式
- Celery `execute_agent_task` 已注册，SSE 端点 `/tasks/{id}/stream/` 已存在

### 1.2 目标

**实现真正的多智能体协作能力**，而非把前端假演示搬到后端。8 个剧本只是历史包袱，不是方案主轴。

具体交付四项能力：

1. **事件完整性** — 协作过程的每一步落库，可回放、可审计
2. **真实工具执行** — subtask 能调用 22 个已注册工具，而非仅生成文本
3. **可续传、可中断** — SSE 断线从任意 sequence 续传，任务可暂停 / 恢复 / 取消
4. **写操作可追溯可回滚** — agent 的每次写库带 origin 标记，update / create 可撤销

### 1.3 已确认的架构决策

| 维度 | 决策 |
|---|---|
| 通用层边界 | 通用编排引擎，剧本降为示例入口，不逐场景补后端 |
| LLM 参与度 | 真实 LLM 规划 + 真实工具执行 |
| 执行链路 | Celery 执行 + `AgentEvent` 单一事实来源 + SSE 断点续传 |
| 工具 schema | 基类从 `get_schema()` 自动降级生成通用 schema，22 工具立即全部对 LLM 可见 |
| 外发落点 | 可插拔 notify 通道，内网默认站内通知，工具层只暴露 `notify` |
| 写库安全 | 真落库 + origin 标记可回滚 |

## 2. 根因分析

### 2.1 断链的单点根因

`smart_assistant/tasks.py:142-146` 构造执行器时只传了 3 个参数：

```python
executor = MultiAgentExecutor(
    task_packet=task_packet,
    llm_router=llm_router,
    tool_registry=ToolRegistry,
)
```

而 `agents/executor.py:76-84` 的签名**早已预留**注入口：

```python
hook_registry: Any | None = None,
event_bus: EventBus | None = None,
agent_task_id: str | None = None,  # Plan 3: DB 持久化 + 断点恢复用
```

三个后果连锁：

1. `self.event_bus = event_bus or EventBus()`（`:89`）自建纯内存 bus，`PipelineRunner`(`:102`) 与 `SubTaskRunner`(`:91`) 的 14 处 emit 全部丢在内存
2. `agent_task_id=None` → `AuditLogHook._write_agent_event`(`hooks/builtin/audit_log.py:298-300`) 直接早退
3. `CheckpointManager(None)` → 断点恢复能力失效

`event_bus` 已透传给 `SubTaskRunner` 与 `PipelineRunner`，因此**持久化桥不需要改 executor 签名**，只需子类化 `EventBus` 并在 Celery 任务里补传参数。

### 2.2 多智能体路径完全不执行工具

`agents/` 全域 grep `ToolRegistry` 仅 4 处命中，全在 `executor.py`：`:80` 构造参数、`:87` 赋值、`:342` resume 透传、`:47` 注释。**存下来之后从未被读取。**

`subtask_runner.py` 275 行全文无任何 `tool` 字样。`run()` 的流程是 `to_context_for → invoke_llm → parse_output`，纯 LLM 文本生成，解析出 JSON 就当产物。

**结论**：22 个工具在多智能体路径上从未被触达。真正会调工具的是单轮 chat 路径（`agent/tool_rounds_runner.py`），两条链路完全独立。"真实工具执行"需要新增能力，不是补一行 emit。

### 2.3 `AuditLogHook` 在生产路径零实例化

`hooks/base.py:205-206` 的 `registry.register(...)` 是 docstring 里的 Example，不是代码。真实注册在 `hooks/wiring.py:register_builtin_hooks()`，只挂了 `PiiMaskingHook` / `TimeoutGuardHook` / `ConfirmationHook` / `RateLimitHook`。

`wiring.py` 模块文档自述："审计钩子需要按任务实例化（`agent_task_id`），**由多 Agent 执行器自行持有**" —— 而执行器从未实例化它。生产代码中 `AuditLogHook(` 调用点数量为 0。

**推论**：`AgentEvent` 不存在"多写入者竞态"，因为 hook 侧从未写入。`PersistentEventBus` 可以成为唯一写入者，sequence 分配退化为实例内计数器，无需数据库序列或行锁。

### 2.4 状态机不闭合

`AgentTask.STATUS_CHOICES` 只有 `pending` / `running` / `paused` / `completed` / `failed` / `cancelled`。而：

- `executor._classify_status()`（`:174-182`）在部分 subtask 失败时返回 `partial`
- `executor._execute_by_mode()`（`:157-170`）对 FANOUT / HIERARCHICAL 返回 `rejected`
- `tasks.py:152` 是 `task.status = result.status` 直写

Django 的 `CharField(choices=...)` 只在 `full_clean()` 校验，`save()` 不校验，因此这两个值会**静默落库成非法状态**。后果：`views/tasks.py:271` 的终止判断认不出它们，SSE 空转到 60 秒超时；`execute` 的 `status != "pending"` 校验也拦不住重复执行。

### 2.5 事件类型缺失

`AgentEvent.EVENT_TYPE_CHOICES` 缺 `subtask.skipped`（`pipeline.py:82/95/109/135` 四处 emit）与 `task.aborted`（`pipeline.py:129`）。目前无害是因为这些事件从未落库；一旦接上持久化桥，立刻变成非法 `event_type` 写进表里。

### 2.6 SSE 端点的既有缺陷

`views/tasks.py:249-278`：

| 位置 | 缺陷 |
|---|---|
| `:250` | `last_seq = 0` 硬编码，每次连接从头回放 |
| `:256` | 缺 `select_related("subtask")`，`:262` 每 500ms 一轮 N+1（`timeline` `:297` 已有，R5 优化漏了这处） |
| `:266` | 手拼 `data:` 帧，不走 `sse_event()`，无 `format_version`、无 `id:` 行 |
| `:271` | 终止集合缺 `paused` / `partial`，暂停任务空转到超时 |
| `:278` | `timeout` 帧在 `while` 外无条件执行，`break` 后仍多发一条 |
| `done` / `timeout` 帧 | 不带 `sequence`，前端无法从终止帧推进续传锚点 |

### 2.7 并发闸门缺失

- `create_from_query`（`:109-168`）整段无 `transaction.atomic`，Supervisor 失败留孤儿 task
- `execute`（`:181-190`）裸读 `status != "pending"` 后 `.delay()`，与 `intervene` resume（`:221-231`）之间无锁，可双发同一 task
- `intervene` 三分支全部裸 `task.save()`；`cancel`（`:233-234`）无任何状态校验

项目内**已存在正确范式** —— `executor.resume_from_checkpoint`（`:312-320`）：

```python
with transaction.atomic():
    agent_task = AgentTask.objects.select_for_update().get(task_id=task_id)
    if agent_task.status == "running":
        return TaskResult(task_id=task_id, status="failed",
                          error_message=f"AgentTask {task_id} 已在运行中,拒绝并发恢复")
```

### 2.8 超时不匹配

| 层 | 当前值 | 位置 |
|---|---|---|
| Celery 硬超时 | 300s | `tasks.py:95` |
| Celery 软超时 | 240s | `tasks.py:96` |
| 单次 LLM 请求 | 120s（硬编码） | `router.py:32` |
| 单 subtask max_tokens | 2000–8000 | `roles.py:60` |
| 全局 token 预算 | 20000 | `models.py:286` |

20000 预算支持 3–8 个 subtask，每个至少一次 LLM 调用。最坏 8 × 120s = 960s，是硬超时的 3 倍。

另有 `tasks.py:212-213` 的 `except AgentTask.DoesNotExist: raise ValueError` 会被 `autoretry_for=(Exception,)` 捕获，对不存在的 task 白重试 2 次（每次 backoff 60s）。

### 2.9 工具 schema 硬阻塞

`tools/base.py:110` 的 `get_openai_tool_schema()` 故意不标 `@abstractmethod`（为兼容 18 个既有子类），未实现时运行期 `raise NotImplementedError`（`:130`）。因此 `registry.get_openai_tools()`（`:66`）在构建工具列表时就会抛异常 —— 原生 tool calling 对多数工具不可用。

## 3. 编排入口与执行链

### 3.1 `PersistentEventBus`

`EventBus`（`agents/dataclasses.py:93`）保持纯内存不动，测试与非持久化场景仍依赖它。新增子类 `agents/persistent_event_bus.py`：

```
PersistentEventBus(EventBus)
  __init__(self, task: AgentTask)
      self._task = task
      self._seq = 已有事件的 max(sequence)（新任务为 0）
      self._subtask_pk_map = {subtask_id: pk}   一次性预加载
      self._dropped = 0

  emit(event_type, payload)
      super().emit(...)                          # 内存副本保留，get_events() 仍可用
      try: AgentEvent.objects.create(...)        # DB 写
      except: self._dropped += 1; logger.error   # 不中断编排
```

四个设计要点：

**唯一写入者。** 由 2.3 的结论，`AuditLogHook` 在生产从未实例化，`tasks.py` 三处手写 `AgentEvent` 将被移除（见 3.5），因此 `PersistentEventBus` 是 `AgentEvent` 的唯一写入者。sequence 用实例内计数器即可，**不需要 `event_seq` 字段、不需要行锁、不需要 migration**。

**emit 不因写库失败而中断编排。** 事件是可观测性，不是业务正确性。但失败必须计数并在 `task.completed` 的 payload 里带 `dropped_events: N` —— 不能像 `audit_log.py:328-329` 那样静默 warning，否则事件丢了无人知晓。

**时间戳由 DB 生成。** `Event.timestamp` 是 naive `datetime.now()`（`dataclasses.py:87`），落库时不用它，让 `AgentEvent.created_at`（`auto_now_add`）生成 —— 顺带绕开 `USE_TZ=True` 下的时区偏移，且保证 sequence 与 created_at 单调一致。

**`subtask` FK 从 payload 反查。** `EventBus.emit` 只有 `(event_type, payload)` 两个参数，拿不到 `AgentSubTask` 实例。`PipelineRunner` / `SubTaskRunner` 的 emit 均在 payload 里带 `subtask_id`，构造时预加载 `{subtask_id: pk}` map，避免每次 emit 回表。

### 3.2 状态机闭合

三处改动，缺一不可：

- `AgentTask.STATUS_CHOICES` 新增 `("partial", "部分完成")`。它是 `_classify_status` 的正常返回值，必须是合法终态。
- `rejected` **不进 choices**。FANOUT / HIERARCHICAL 未实现是配置错误而非任务终态；给它发明一个终态会让状态机多一条永不推进的死路。在 `tasks.py` 落库前映射为 `failed` + `error_message`，SSE 终止判断、重试逻辑、前端渲染即自动正确。
- `AgentEvent.EVENT_TYPE_CHOICES` 新增 `("subtask.skipped", "子任务跳过")`、`("task.aborted", "任务中止")`、`("subtask.tool_result", "子任务工具结果")`（第三个见 4.3）。

`views/tasks.py:271` 与前端 `agentTaskApi.js` 的终止集合同步加入 `partial`、`paused`。

### 3.3 并发闸门

照抄 `executor.py:312-320` 的既有范式，四处补齐：

| 位置 | 现状 | 改为 |
|---|---|---|
| `create_from_query` `:109-168` | 无 atomic | 整段包 `atomic()`，`AgentTask` + N 个 `AgentSubTask` 同事务 |
| `execute` `:181-190` | 裸读状态后 `.delay()` | `atomic + select_for_update`，状态断言与派发之间无窗口 |
| `intervene` resume `:221-231` | 裸 `save()` 后 `.delay()` | 同上 |
| `intervene` pause / cancel `:213` / `:233` | 裸 `save()`，cancel 无校验 | 加锁；cancel 拒绝已终态（completed / failed / partial / cancelled） |

**`.delay()` 移入 `transaction.on_commit`。** 现在是先派发再让请求事务提交，worker 可能在 `status="running"` 落库前就 `get()` 到旧行。

### 3.4 超时按预算换算

- `router.py:32` 的 `REQUEST_TIMEOUT` 改为读 `settings.LLM_REQUEST_TIMEOUT_SECONDS`（default 120），Docker env 可覆盖
- Celery 超时改为**派发时逐任务计算并传入**：`apply_async(..., soft_time_limit=计算值, time_limit=计算值+60)`，计算式为 `min(subtask 数 × LLM_REQUEST_TIMEOUT × 重试系数, AGENT_TASK_MAX_SECONDS)`，上限进 settings（default 1800）
- 装饰器上的 `task_time_limit` / `task_soft_time_limit` 保留作兜底，调至与上限一致
- `tasks.py:212-213` 的 `AgentTask.DoesNotExist → ValueError` 改为记日志后正常返回，不触发 autoretry
- `settings/base.py:419` 的 `TOOL_CALLS_TIMEOUT_SECONDS` 目前零消费点，接到 `tool_rounds_runner` 上

### 3.5 `tasks.py` 收尾

- `:142-146` 补传 `event_bus=PersistentEventBus(task)`、`agent_task_id=str(task.task_id)`
- 删除 `:135` / `:196` / `:224` 三处手写 `AgentEvent` —— `executor.execute()` 已 emit `task.started`(`:115`)、`task.completed`(`:213`)、`task.failed`(`:139`)，接上桥后手写会变成重复事件
- `:170-184` 循环内逐条 `subtask_obj.save()` 改 `bulk_update`
- happy path 的状态写入包进 `atomic()`

## 4. 事件契约统一

### 4.1 两套 SSE 契约合流

| | 单轮 chat 流 | 多智能体任务流 |
|---|---|---|
| 序列化出口 | `sse_contract.sse_event()` 唯一 | `views/tasks.py:266` 手拼 |
| 版本标记 | 注入 `format_version = 1` | 无 |
| 错误分类 | `classify_error_kind()` 四档 | 无 |

合流方向：**多智能体流改走 `sse_event()`**，获得 `format_version` 与统一错误分类。

**不做的事**：不把两套事件类型合成一个枚举。`chunk` / `meta` / `confirmation` 是 token 流语义，`subtask.*` 是任务编排语义，强行统一会让两边都变形。共享的是**信封**（序列化出口、版本号、错误分类），不是**载荷**。

`done` 与 `timeout` 帧一并过同一出口，顺带解决它们不带 `sequence` 的问题。

### 4.2 前端事件类型映射

后端 18 个 `event_type` → 前端 5 个 `type`。映射放前端适配层，**不在后端迁就前端**：

| 后端 `event_type` | 前端 `type` | 渲染 |
|---|---|---|
| `subtask.started` | `thinking` | AgentCard 开始态 |
| `subtask.progress` | `thinking` | 追加内容 |
| `subtask.tool_call` | `tool_call` | ToolCallCard |
| `subtask.tool_result` | `tool_result` | ToolCallCard 结果区 |
| `subtask.completed` | `thinking` 收尾 | AgentCard 完成态 |
| `task.completed` | `final_answer` | FinalAnswerCard |
| `subtask.skipped` / `subtask.failed` / `task.failed` / `task.aborted` | `error`（新增） | 需新增渲染分支 |

`error` 这个 type 前端目前不存在 —— 剧本回放里不会失败，所以从未设计失败态渲染。这是从假演示转真功能必然要补的 UI。

### 4.3 工具执行能力（本节核心）

由 2.2 的结论，`tool_call` / `tool_result` 的 emit 点尚不存在，需先让 subtask 具备调工具的能力。两条路径：

**路径 I：subtask 内嵌 tool-calling 循环**
在 `SubTaskRunner.run()` 里把 `invoke_llm` 换成 `generate_with_tools`（`router.py:174` 已有），拿到 `tool_calls` 后经 `ToolRegistry.get_tool_for_user()` 执行，结果回灌继续下一轮，直到 LLM 不再要求工具。本质是把 `agent/tool_rounds_runner.py` 的既有能力搬进 subtask 层。

**路径 II：工具调用作为独立 subtask 角色**
Supervisor 规划时就决定调哪个工具，写进 `subtask.inputs`，`SubTaskRunner` 按类型分派。

**采用路径 I**，三个理由：

1. `generate_with_tools` 与 `get_openai_tools()` 已存在且配对，加上 4.4 的 schema 降级，22 工具立即可见
2. 工具选择交给执行时的 LLM，避免 Supervisor 在不知道中间结果的情况下预判工具参数
3. `tool_rounds_runner` 已有的轮次上限、`tool_choice="none"` 收尾等控制逻辑可复用而非重写

代价：subtask 的 token 消耗变得不可预估（工具结果回灌会放大），`global_budget` 默认 20000 多半要上调，具体数值按实测定。

emit 点随之确定，都在 tool-calling 循环内：LLM 返回 `tool_calls` 时 emit `subtask.tool_call`（payload 带 `tool` / `arguments` / `round`），工具返回后 emit `subtask.tool_result`。

**用两个独立 event_type 而非一个带 `phase` 字段**：前端按 type 分流渲染，用 payload 里的 phase 分流意味着渲染层要拆 payload 才知道往哪画；且 choices 本就在改，多加一个不增成本。

### 4.4 工具 schema 降级

`tools/base.py` 的 `get_openai_tool_schema()` 从 `raise NotImplementedError` 改为**从 `get_schema()` 自动降级生成**：

```
{
  "type": "function",
  "function": {
    "name": cls.intent_type,
    "description": cls.description,
    "parameters": {
      "type": "object",
      "properties": {"query": {"type": "string", "description": "自然语言查询"}},
      "required": ["query"],
      "additionalProperties": False
    }
  }
}
```

单 `query` 字符串参数恰好吻合多数工具当前 `execute(query, context)` 的实际签名。已手写精确 schema 的子类（如 `MemoUpdateTool`）覆盖基类实现，不受影响。

`registry.assert_all_have_openai_schema()`（`:166`）的 CI lint 语义随之从"检查是否实现"改为"检查 schema 结构合法"。

精确参数按使用频次增量补充，不作为前置门槛。

### 4.5 断点续传

`views/tasks.py:250` 的硬编码 `last_seq = 0` 改为读 query param（`?last_seq=N`），缺省 0。

**不用 `Last-Event-ID` header**：客户端是 `authFetch` + `getReader()`（`agentTaskApi.js:171`），不是 `EventSource`，浏览器不会自动回发该 header。原生 `EventSource` 在本项目不可用 —— 它不支持自定义 header（带不了 JWT），且 IE11 无此 API。

配套四处（对应 2.6 的缺陷表）：

- 帧内加 `id:` 行（值 = sequence），让 SSE 结构合规
- 终止集合补 `paused` 与 `partial`
- `timeout` 帧移入 `while` 的正常退出分支
- `:256` 补 `select_related("subtask")`

### 4.6 心跳保活

轮询 `time.sleep(0.5)` 保留 —— `AgentEvent` 是 DB 表，无 pub/sub，改推送需引 Redis channel，超出本次范围。但无事件时段发心跳注释帧（`: ping\n\n`），间隔 15s，否则 nginx 与前端 fetch 在纯静默时可能判死连接。

## 5. 写操作 origin 标记与回滚

### 5.1 约束与排除项

项目**无审计 / 版本库依赖**（`simple-history` / `django-reversion` / `auditlog` 均不在 requirements）。加装新依赖违反离线优先（要进离线镜像），因此自己实现。

写工具实际只覆盖 3 个业务面：`Memo`（create / update / delete）、`SwapRequest`（create / decide）、office 文件生成（不写业务表）。回滚要处理的面比 22 个工具的数字暗示的小得多。

三条排除的歧路：

- **不加通用版本表**（每张业务表存前后快照）。没有现成库就自己做等于重造一个半成品版本控制，而实际写面只有 3 个模型。
- **不给业务模型加 `origin` 字段**。要改 `Memo` / `SwapRequest` 的 schema，还要求所有未来写工具都记得加；侵入业务模型换来的只是"知道某条记录是 agent 写的"。
- **不用 delete 做回滚**。`MemoDeleteTool:349` 已是硬 `memo.delete()`，用第二次硬删撤销一次创建，等于把 agent 的错误放大成数据丢失。

### 5.2 旁路写操作日志

新增 `smart_assistant.AgentWriteLog`，与业务表解耦：

| 字段 | 类型 | 说明 |
|---|---|---|
| `task` | FK → AgentTask (null) | 单轮 chat 路径也写，故可空 |
| `session_id` | CharField | 会话 id，非 FK，跨路径通用 |
| `user` | FK → CustomUser | 触发人 |
| `tool_name` | CharField | `memo_create` / `memo_update` / … |
| `target_model` | CharField | `"memos.Memo"` |
| `target_pk` | CharField | 写入后的主键；create 前为空 |
| `operation` | CharField | `create` / `update` / `delete` |
| `before` | JSONField | update / delete 的原值；create 为 null |
| `after` | JSONField | create / update 的新值；delete 为 null |
| `reverted_at` | DateTimeField | null = 仍生效 |
| `reverted_by` | FK → CustomUser | null |
| `created_at` | DateTimeField | `auto_now_add` |

三个设计决策：

**`before` / `after` 存字段级 dict，不存整行序列化。** 由工具声明哪些字段参与回滚（`MemoUpdateTool` 就是 `title` / `content` / `reminder_time`，正好是 `:187` `update_fields` 的内容）。整行快照会把 `updated_at`、外键 id、将来新增字段一起冻结，回滚时反而要判断哪些能写回；字段级声明让回滚变成确定的 `setattr` + `save(update_fields=...)`。

**`target_model` 存字符串而非 ContentType FK。** ContentType 的价值是级联与反查，这里两者都不需要；字符串在离线包 / 数据迁移时也不会因 content_type id 漂移而错位。回滚时 `apps.get_model()` 解析。

**记录点在工具的 `confirmed` 分支内、与业务写同一个 `transaction.atomic`。** `memo_write_tools_v2.py` 已 `from django.db import transaction`。原子成对保证不会出现"业务改了但没日志"（回滚不到）或"日志有但业务没改"（回滚出幻影）。

### 5.3 回滚语义

| operation | 回滚动作 | 可逆性 |
|---|---|---|
| `create` | 走业务撤销路径（软删置位） | 完全可逆 |
| `update` | `before` 的字段写回 | 完全可逆 |
| `delete` | **不可回滚**，日志仅供审计 | 不可逆 |

`create` 的回滚不用 delete。`Memo` 无软删字段（models 全文只有 `is_completed` / `reminder_sent`），因此给 `Memo` 加 `is_deleted` + `deleted_at`，回滚置位而非物理删。**这是本方案唯一需要动业务模型的地方**，且顺带把 `MemoDeleteTool:349` 的硬删改成软删 —— 那个硬删本身就是隐患，agent 误删一条备忘录目前无法挽回。

`delete` 声明为不可逆，而非硬造一个"从 `before` 快照重建记录"：重建会得到新主键，所有指向原记录的引用全部失效，是假的可逆。老实标不可逆，配合 `require_confirmation=True` 的前置确认，比给一个骗人的撤销按钮诚实。

### 5.4 回滚入口

`POST /api/smart-assistant/write-logs/{id}/revert/`，`IsAuthenticated` + 归属校验（只能撤销 `user=request.user` 的日志；管理员越权需另开权限，本次不做）。

四条闸门：

1. `atomic + select_for_update` 锁日志行，`reverted_at` 非空直接 409（防重复撤销）
2. `operation == "delete"` 返回 400 + 明确原因
3. **回滚前校验当前值与 `after` 一致**；不一致（记录在 agent 写入后被人手工改过）返回 409 并回显差异，不盲目覆盖 —— 静默覆盖用户的手工修改比拒绝撤销糟糕得多
4. 回滚本身也写一条 `AgentWriteLog`（`operation="update"`，`task=None`，标注 `revert_of=<原日志 id>`），撤销动作自身可审计

配套 `GET /api/smart-assistant/write-logs/?task_id=` 列出某任务的全部写操作，供前端在 `FinalAnswerCard` 下方渲染"本次任务改了 3 条数据 [撤销]"。这是"origin 标记可回滚"对用户可见的落点。

### 5.5 notify 不进 AgentWriteLog

通知一旦送达无法撤回。`AgentWriteLog` 的语义是"可回滚的写"，放进去会给出假的撤销入口。notify 的可审计性靠 `AgentEvent` 的 `subtask.tool_call` payload。

## 6. notify 通道

### 6.1 前置修复：收紧 NotificationViewSet

`notifications/views.py:11` 是全开的 `ModelViewSet`，`permission_classes` 只有 `IsAuthenticated`。`get_queryset()` 按 `user=request.user` 隔离只管住了读，**`create` 完全无约束** —— 任何登录用户可 POST 伪造任意 `type` / `priority` / `is_system=True` 的通知，还绕过 `NotificationService` 的 24h dedupe。

这是既有安全洞，与 agent 无关，但 agent 一旦有 notify 能力，该路径就成了绕过 service 的后门。

改为 `ReadOnlyModelViewSet`，保留 `unread_count` / `mark_read` / `mark_all_read` 三个 `@action`（前端铃铛依赖）。前端 `notificationApi.js:5-11` 只用 list / unread_count / mark_read，故为纯收紧无破坏。

**实施时排在最前，独立于 agent 功能进度。**

### 6.2 通道抽象

新增 `notifications/channels/` 包：

```
NotifyChannel (ABC)
  name: str
  send(*, user, title, content, link, priority, dedupe_key, meta) -> NotifyResult

InAppChannel(NotifyChannel)          # 默认，内网唯一可用
  name = "in_app"
  send() → 委托 NotificationService.create(...)

# 将来：EmailChannel / SmsChannel
```

`NotifyResult` 是小 dataclass：`{delivered: bool, channel: str, ref: str, message: str}`。`ref` 存 `Notification.id`（in_app）或将来的 message-id（email），让工具返回值带上可追溯凭据。

**driver 选择走 `NotificationPreference.channel_settings`**，不是 settings 全局开关。该字段（JSON，形如 `{"email": {...}, "sms": {...}}`）已存在但零消费方，语义正好是"这个用户希望走哪些通道"。全局 settings 无法表达"某人要邮件、某人只要站内"，而内网将来接邮件恰是这种混合场景。为空或无匹配 driver 时回落 `in_app`，现有用户零配置可用。

**分发是扇出而非路由**：启用了多个通道就都发。不设"主通道失败降级到备用" —— 通知的失败降级会产生"用户收到两遍"或"以为发了其实没发"的歧义。

### 6.3 通用通知类型

`Notification.TYPE_CHOICES` 现有 24 个值全部绑定具体业务（`schedule_change` / `memo_due` / `paperless_down` …），没有一个可供 agent 使用。新增两个：

- `("agent_notify", "智能助手通知")` — agent 主动发起的外发
- `("agent_task_result", "智能助手任务结果")` — 任务完成 / 失败的结果投递

**agent 只用这两个，不允许冒用业务类型。** 前端通知中心按 type 分组筛选，agent 通知混进 `schedule_change` 会污染业务筛选；且用户要能一眼分辨"这条是 AI 发的"。

`priority` 固定 `PRIORITY_NORMAL`，**不让 LLM 决定优先级** —— 否则 prompt 稍加诱导就能让 agent 发 `PRIORITY_URGENT`。需要高优先级的场景由业务代码显式调 service。

### 6.4 NotifyTool

新增 `smart_assistant/tools/notify_tool.py`：`risk_level = "write"`，`require_confirmation = True`。

四个约束，逐条都是安全边界：

**收件人必须解析到真实用户且受 scope 约束。** LLM 给的是自然语言（"通知张三"），经 `personnel` / `users` 查询解析。解析出 0 个或 >1 个候选**直接拒绝，不猜** —— 照抄 `memo_write_tools_v2` 的多候选拒绝范式（其注释写明"防止误改/误删"，同理防误发）。可发范围受 `SmartAssistantScope` 限制：`SELF` 只能发给自己，`DEPARTMENT` 限本部门，`GLOBAL` 才能全员。

**收件人数量硬上限 10 人**，超出拒绝。防止 LLM 被诱导做全员群发 —— 这是内网环境里 agent 能造成的最大噪音。批量通知走业务代码的 `bulk_create` 路径（`signals.py:73-88` 已有），不经 agent。

**走 `dry_run` / `confirmed` 两阶段**（沿用 `memo_write_tools_v2.py:77-86` 的现成契约）。`dry_run` 返回 draft：解析出的收件人列表 + 标题 + 正文，用户确认后才真发。`ConfirmationHook` 已在 `wiring.py` 注册（PRE_EXECUTE priority=20），无需新接线。

**`get_openai_tool_schema()` 手写而非走 4.4 的基类降级。** notify 是唯一参数结构真正需要精确的写工具 —— 收件人 / 标题 / 正文三个语义完全不同的字段挤进单个 `query` 字符串会显著提高解析失败率。基类降级适用于 21 个 read 工具，notify 例外。

审计：`AgentEvent` 的 `subtask.tool_call` payload 带收件人 id 列表**与姓名**、标题、正文。写姓名而非仅 id，否则事后审计要回表拼人名。

### 6.5 任务结果投递

多智能体任务达到终态（`task.completed` / `task.failed` / `partial`）时自动给发起人发一条 `agent_task_result` 通知，`link` 指向任务时间线页。

理由：Celery 任务动辄数分钟，用户不会盯着 SSE 等。现在任务跑完若用户已关页面，结果就丢在 DB 里无人知晓。这条投递让长任务真正可用 —— 也是真功能与演示的一个实质差别（演示时用户当然在看屏幕）。

落点在 `tasks.py` 的终态写入处，`dedupe_key = f"agent_task:{task_id}"` 防重试重复投递。不经 `NotifyTool`（不需要 LLM 参与、不需要确认），直接调 `InAppChannel`。

## 7. 前端 SSE 订阅替换

### 7.1 新 hook：useAgentTaskStream

替换 `useScenarioPlayer`，保持相同返回形状以免动 UI：

```js
useAgentTaskStream({ taskId })
  → { state, pause, resume, cancel, retry }
  state = { events, status, taskId, lastSequence, error }
```

`ScenarioCollabCard` 只消费 `state.events` / `state.status` 与 5 个动作，渲染层（`AgentCollabStream` / `AuditTimeline`）只吃 events 数组和三个布尔，因此 hook 是唯一接缝。

三个关键差异：

**`start` 消失。** 任务由 `useSmartChat` 创建（`POST /tasks/create/` → `POST /{id}/execute/`），hook 只负责订阅一个已存在的 taskId。原 `useEffect(() => start(...))` 改为按 taskId 订阅；StrictMode 双调用问题依然存在，但 `subscribeTaskStream` 返回 `{abort}`，cleanup 里 abort 即可，比 timer 版本干净。

**`reset` → `cancel` + `retry`。** 真任务已在服务端跑过，事件在 DB 里，"重置"无对应语义。`cancel` 走 `intervene cancel`，`retry` 用同一 objective 新建任务（新 taskId，新卡片）。**不保留叫"重置"的按钮** —— 留着会让用户以为能重放。

**新增 `error` 与 `lastSequence`。** 前者承接 4.2 的失败态渲染，后者是续传锚点。

### 7.2 事件映射层

后端 18 个 `event_type` → 前端 5 个 `type` 的映射放独立纯函数 `mapAgentEvent(backendEvent)`，不放 hook 里：纯数据转换好测，且 `AuditTimeline` 的审计导出需要**同时保留原始 `event_type`** —— 审计不该只看映射后的粗粒度类型。

```js
{
  id: `evt-${sequence}`,   // 用 sequence 做 id，天然去重
  sequence,                 // 续传锚点
  type,                     // thinking | tool_call | tool_result | final_answer | error
  eventType,                // 原始 event_type，审计用
  agent, tool, input, output, content, ts,
}
```

`id` 用 sequence 而非 `Date.now()` 自增，重连产生的重复事件即可按 sequence 去重（`agentTaskApi.js:118` 的注释已声明"重复事件由调用方按 sequence 去重"，但调用方从未实现，因为剧本模式不重连）。

### 7.3 续传与重连

hook 内维护 `lastSequenceRef`，重连时传 `?last_seq=N`。

| 情形 | 动作 |
|---|---|
| `onTimeout`（服务端 60s 空转）且任务未终止 | 立即续订，**无退避** |
| `onError`（网络断） | 指数退避 1s / 2s / 4s，3 次后置 `error` |
| `onDone` 且状态是终态 | 不重连 |
| 组件卸载 | `abort()` |

`onTimeout` 不退避是有意的：60s 超时是服务端设计行为（`views/tasks.py:251`），长任务必然反复触发，退避会让进度显示卡顿。`onError` 是真故障，需要退避。

配套修 `agentTaskApi.js` 三处：

- `parts.some(dispatch)`（`:209`）改为 `forEach` + 独立终止标记。`dispatch` 对 `done` / `timeout` 返回 `true` 使 `some` 短路 `return`，**同一批 parts 中排在其后的帧被丢弃** —— 现在无害（done 是最后一帧），但加了续传后，重连若在一批里收到 `timeout` + 后续事件，事件会丢
- `subscribeTaskStream(taskId, callbacks, { lastSeq })` 加第三参数，拼进 query
- `onDone` 回调带上 `sequence`

### 7.4 pause / resume 的中间态

`pause` / `resume` 从本地 timer 控制（即时、无失败可能）变为服务端状态变更（有延迟、会失败）。`state.status` 从 4 值扩到 7 值：

```
idle → running → { pausing → paused → resuming → running } → completed | failed | partial | cancelled
```

`pausing` / `resuming` 是纯前端乐观态：点击后立即置位并禁用按钮，收到后端 `task.paused` / `task.resumed` 事件后转正式态。5s 内未收到对应事件则回滚原状态并提示失败 —— 不无限等，也不假装成功。

这是本节唯一必须改 UI 的地方（`AgentCollabStream` / `AuditTimeline` / `AgentCard` / `ToolCallCard` / `FinalAnswerCard` 五个组件不动，除 7.5）。

### 7.5 失败态渲染

`type: 'error'` 需要新增渲染分支：哪个 subtask 失败、原因（`payload.error`）、已重试次数、后续是跳过还是终止。

`FinalAnswerCard` 在 `status` 为 `failed` / `partial` 时也要变形。**`partial` 尤其重要**：部分 subtask 成功意味着有部分产出，不能因为整体不是 `success` 就什么都不显示。

### 7.6 拆掉剧本互斥分支

`useSmartChat.js:351-373`（命中剧本则注入 `collab_card` 并跳过 `runStream`）删除。改为：

- `matchScenarioByInput` 从"拦截并回放"降为**输入框的示例提问提示**（8 个剧本的 `userInput` 变成快捷入口按钮）
- 用户提问统一走 `runStream`；**何时升级为多智能体任务由后端决定**，不在前端按关键词判断 —— 这是"通用编排，剧本只做示例入口"的落地

后端升级判据分两阶段：

- **阶段一**：显式入口（用户点"复杂任务"按钮），避免自动判据的不确定性
- **阶段二**：单轮路径的 LLM 通过 `escalate_to_task` 工具主动升级，零额外 LLM 调用。依赖 4.3 的工具执行能力先落地

不采用"每次提问先跑一次 Supervisor 预判"，那会给每个普通问题都加一次 LLM 调用。

`scenarios.js`（1270 行）的 `steps` 数组全部删除，只留 `id` / `title` / `userInput` / `icon` 作示例入口，文件缩至约 80 行。

### 7.7 IE11 降级

`response.body.getReader()` **IE11 不支持**（无 `ReadableStream`）。现有代码 `agentTaskApi.js:167` 已有可用性检测但只是报错。IE11 下降级为**轮询 `/timeline/`**（该端点已存在，`views/tasks.py:285`），每 2s 拉全量事件按 sequence 去重。

此降级路径必须实现，否则 Win7 / IE11 用户完全用不了多智能体功能。

无新增 npm 依赖（`dayjs` / `antd` 已在），符合离线优先。

## 8. 数据库迁移清单

| app | 变更 | 破坏性 |
|---|---|---|
| `smart_assistant` | 新增 `AgentWriteLog` 表 | 无（新表） |
| `smart_assistant` | `AgentTask.STATUS_CHOICES` 加 `partial` | 无（choices 为 no-op） |
| `smart_assistant` | `AgentEvent.EVENT_TYPE_CHOICES` 加 3 值 | 无（同上） |
| `notifications` | `Notification.TYPE_CHOICES` 加 2 值 | 无（同上） |
| `memos` | `Memo` 加 `is_deleted` + `deleted_at` | **需审计所有查询点** |

`memos` 那项是唯一有风险的：加字段本身安全（有 default），但**所有查 `Memo` 的地方都要过滤 `is_deleted=False`，漏一处就会让软删记录重新出现在用户面前**。需全量 grep `Memo.objects` 并逐处处理。

按 CLAUDE.md：迁移前先 `python manage.py check_migrations`，再 `python manage.py backup_db`，然后显式 `migrate`。

choices 变更虽是 no-op，仍要生成迁移以保持 migration 状态一致。

## 9. 风险与依赖

| 风险 | 影响 | 缓解 |
|---|---|---|
| `Memo` 软删漏改查询点 | 已删备忘录重新出现 | 全量 grep + 测试覆盖每个查询入口 |
| tool-calling 循环使 token 消耗不可预估 | 预算耗尽 subtask 被跳过 | `global_budget` 按实测上调；`pipeline.py:108-119` 的预算闸门已存在 |
| Celery 超时按预算换算后仍不足 | 长任务被杀 | `AGENT_TASK_MAX_SECONDS` 可配；checkpoint 恢复已存在 |
| 前端映射层与后端 event_type 漂移 | 事件渲染不出来 | `mapAgentEvent` 对未知 type 走 `thinking` 兜底并 console.warn |
| IE11 轮询降级未测 | Win7 用户不可用 | 降级路径纳入验收清单 |
| 基类 schema 降级后 LLM 传参质量下降 | 工具调用失败率上升 | 按使用频次增量补精确 schema；`validate_arguments` 已有 |

外部依赖：无新增 Python / npm 包。

## 10. 不在本次范围

- FANOUT / HIERARCHICAL 执行模式（`Supervisor.generate_task_packet` `supervisor.py:87` 与 `executor._execute_by_mode` 双重拒绝，保持拒绝）
- `AgentEvent` 从轮询改 Redis pub/sub 推送
- 单轮 chat 路径补 token 预算
- `office_assistant` app 域补工具（该域目前无任何工具）
- 管理员越权撤销他人的 `AgentWriteLog`
- `SwapRequest` 写工具的回滚（`swap_request_decide` 的撤销涉及业务状态机，需单独设计）

## 11. 验收标准

1. 发起一个多智能体任务，`AgentEvent` 表中出现完整事件链：`task.started` → 每个 subtask 的 `started` / `tool_call` / `tool_result` / `completed` → `task.completed`，sequence 连续无空洞
2. 任务执行中断开 SSE 连接再重连，不重复收到已有事件，且能收到断开期间产生的事件
3. 任务执行中点暂停，5s 内 UI 显示已暂停，`AgentTask.status == "paused"`，Celery worker 停在 subtask 边界
4. 部分 subtask 失败的任务，`AgentTask.status == "partial"`，前端显示已成功部分的产出而非空白
5. agent 通过 `memo_update` 改一条备忘录后，`AgentWriteLog` 有对应记录，调 revert 接口后备忘录恢复原值
6. 手工改过的记录调 revert 返回 409 且不覆盖
7. `notify` 工具对 >1 个同名候选拒绝执行，对 >10 收件人拒绝执行
8. 普通用户 POST `/api/notifications/` 返回 405
9. IE11（或禁用 `ReadableStream` 的环境）下任务进度仍可显示
10. 后端 pytest 全绿，覆盖率 ≥80%；前端 Jest 全绿；`npm run build` 无警告
# SAIS Plan 3:多 Agent 复杂任务实战(异常分析报告)

**日期:** 2026-07-17
**分支:** `feat/sa-multi-agent`(从 main 切出)
**依赖:** Plan 1 (f8a01321) + Plan 2 (91b2383b) 已合入 main
**预计工期:** 3-4 天
**Spec 引用:** `docs/superpowers/specs/2026-07-17-smart-assistant-integration-design.md` §2.5

---

## 1. 背景与目标

### 1.1 背景

Plan 1/2 已完成:
- Plan 1:5 个高频 E2E 场景 + 回答级缓存 + cache_version(覆盖率 88.14%)
- Plan 2:多工具链编排升级(Plan 序列化 + 嵌套变量 + 失败策略)

多 Agent 框架已搭好骨架:`supervisor.py` / `executor.py` / `shared_context.py` / `task_packet.py` / `roles.py` / DB 模型(`AgentTask` / `AgentSubTask` / `AgentEvent` 均在 0008 migration)均已就位,**但尚未在真实业务场景中跑通过完整 Pipeline**。

### 1.2 目标

用 1 个复杂任务 **"分析本月所有传感器异常,生成根因报告 + 整改建议"** 真实跑通,验证:
1. Supervisor 任务分解(≥ 3 个 SubTask)
2. Pipeline 模式串行执行 + SharedContext 跨步传递
3. 审计回放(`AgentEvent` 流可重放且状态一致)
4. 断点恢复(kill worker → 重启 → 从 checkpoint 续)

### 1.3 不做

- ❌ Fan-out / Hierarchical 模式(留给后续 milestone,executor 已抛 `NotImplementedError`)
- ❌ 前端 SSE 推送(Plan 4 做)
- ❌ Supervisor 动态介入 / 用户介入交互
- ❌ PIISanitizerHook / SensitiveDataGateHook / ToolTimeoutHook(hooks/builtin 只实现 AuditLogHook)

---

## 2. 涉及的文件与模块

### 2.1 后端修改

| 文件 | 动作 | 说明 |
|---|---|---|
| `omni_desk_backend/smart_assistant/agents/supervisor.py` | **修改** | `_build_system_prompt()` 加入 few-shot 示例,提高 LLM 输出 JSON 稳定性 |
| `omni_desk_backend/smart_assistant/agents/executor.py` | **修改** | 新增 `resume_from_checkpoint()` 方法;每步同步写 `AgentSubTask` / `AgentEvent` 到 DB;新增 `pause()` 方法 |
| `omni_desk_backend/smart_assistant/hooks/builtin/audit_log.py` | **新增** | `AuditLogHook` 实现,统一写 `AgentLog` + `AgentEvent` |
| `omni_desk_backend/smart_assistant/hooks/base.py` | **检查** | 确认 `HookRegistry` 接口与 `AuditLogHook` 对接 |
| `omni_desk_backend/smart_assistant/tasks.py` | **检查** | 确认 Celery task 调用 executor 时传入 DB 持久化参数 |
| `omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py` | **新增** | 复杂任务 E2E + 断点恢复 E2E |
| `omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py` | **新增** | Supervisor 分解测试(4 个) |
| `omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py` | **新增** | 断点恢复测试(5 个) |
| `omni_desk_backend/smart_assistant/tests/test_audit_event.py` | **新增** | 审计事件测试(3 个) |

### 2.2 文档修改

| 文件 | 动作 | 说明 |
|---|---|---|
| `docs/technical/32-smart-assistant-multi-agent.md` | **修改** | 新增"实战 demo:传感器异常分析报告"章节 |

---

## 3. 技术方案

### 3.1 Demo 任务:传感器异常分析报告

**用户问句:** "分析本月所有传感器异常,生成根因报告 + 整改建议"

**Supervisor 分解(预期 ≥ 3 个 SubTask):**

```
Supervisor(LLM 分解)
    ↓
    ├─ SubTask 1: researcher
    │    目标: 采集本月传感器异常数据
    │    工具: sensor_tool
    │    产出: anomalies: [{sensor_id, timestamp, severity, type}]
    │
    ├─ SubTask 2: analyst(依赖 1)
    │    目标: 模式识别 + 异常归因
    │    输入: $researcher.anomalies
    │    产出: root_causes: [{cause, frequency, impact}]
    │
    └─ SubTask 3: writer(依赖 1, 2)
         目标: 撰写根因报告 + 整改建议
         输入: $researcher.anomalies, $analyst.root_causes
         产出: final_report: markdown 文本
```

**SharedContext 流转:**
1. researcher → `ctx.add_artifact("researcher", {"anomalies": [...]})`
2. analyst → `ctx.to_context_for(subtask2)` 自动注入 `$researcher.anomalies`
3. writer → 同时拿到 researcher + analyst 产物

### 3.2 Supervisor few-shot 升级

在 `_build_system_prompt()` 中加一个传感器异常分析的 few-shot 示例(让 LLM 更容易生成合法 JSON):

```python
# 示例:用户问"分析本月传感器异常,生成报告"
FEW_SHOT_EXAMPLE = """
{{
    "objective": "分析本月传感器异常并生成根因报告",
    "execution_mode": "pipeline",
    "subtasks": [
        {{
            "id": "researcher",
            "role": "researcher",
            "objective": "采集本月传感器异常数据",
            "inputs": {{"query": "本月传感器异常记录"}},
            "failure_mode": "retry",
            "depends_on": [],
            "quality_gate": ["anomalies 数量 >= 1"]
        }},
        {{
            "id": "analyst",
            "role": "analyst",
            "objective": "模式识别 + 异常归因",
            "inputs": {{"anomalies": "$researcher.anomalies"}},
            "failure_mode": "retry",
            "depends_on": ["researcher"],
            "quality_gate": ["root_causes 数量 >= 1"]
        }}
    ],
    "final_synthesis": {{
        "id": "writer",
        "role": "writer",
        "objective": "撰写根因报告 + 整改建议",
        "inputs": {{"anomalies": "$researcher.anomalies", "root_causes": "$analyst.root_causes"}},
        "depends_on": ["researcher", "analyst"]
    }},
    "global_budget": 20000,
    "timeout_seconds": 600
}}
"""
```

### 3.3 断点恢复实现

**核心思路:** 每完成一个 SubTask,executor 同步将状态写入 `AgentSubTask` 表(DB)。若 worker 被 kill,重启时:
1. 根据 `task_id` 加载 `AgentTask` + 关联 `AgentSubTask`
2. 找出所有 `status="completed"` 的 subtask,重建 `SharedContext` 的 artifacts
3. 从第一个 `pending` / `running` 的 subtask 继续执行

**代码位置:** `MultiAgentExecutor.resume_from_checkpoint(task_id: str)`

**状态机:**

```
AgentTask.status:
pending → running → completed
                  → paused → running(resume)
                  → failed
                  → cancelled

AgentSubTask.status:
pending → running → completed
                  → failed
                  → skipped
```

**关键约束:**
- 每个 `_run_subtask_with_retry()` 成功返回后立即 `AgentSubTask.objects.update_or_create(status="completed", output=..., tokens_used=...)`
- 每个事件通过 `AuditLogHook` 同步写 `AgentEvent.sequence += 1`
- `resume_from_checkpoint()` 不重跑已 completed 的 subtask,只重跑 pending/running/failed

### 3.4 AuditLogHook 实现

**文件:** `hooks/builtin/audit_log.py`

```python
class AuditLogHook(BaseHook):
    """统一写 AgentLog + AgentEvent

    触发时机:
    - subtask.completed → 写 AgentEvent(sequence)
    - subtask.failed → 写 AgentEvent
    - task.completed → 写 AgentLog(汇总)
    """
    name = "audit_log"

    async def on_subtask_completed(self, event: Event) -> None:
        AgentEvent.objects.create(
            task=self._get_agent_task(),
            subtask=self._get_agent_subtask(event),
            sequence=self._next_sequence(),
            event_type="subtask.completed",
            payload=event.payload,
        )

    async def on_subtask_failed(self, event: Event) -> None: ...
    async def on_task_completed(self, event: Event) -> None: ...
```

**对接:** 在 `MultiAgentExecutor.__init__()` 中,如果传入了 `hook_registry`,注册 `AuditLogHook`。

### 3.5 审计回放验证

**测试方法:**
1. 跑一次完整任务,记录所有 `AgentEvent` 的 `(sequence, event_type, payload)`
2. 根据事件流重建 `SharedContext`(只 replay completed 事件)
3. 断言重建后的 `SharedContext.artifacts` 与原始一致

---

## 4. 实施步骤

### Phase 1:Supervisor few-shot 升级(半天)

- [x] 1.1 在 `supervisor.py` 的 `_build_system_prompt()` 加入 few-shot 示例
- [x] 1.2 写 `test_supervisor_decomposition.py`(5 个测试,含兼容性验证):
  - 标准分解(传感器异常任务 → ≥ 3 SubTask)
  - JSON 校验通过(所有字段合法)
  - 重试机制(第 1 次失败,第 2 次成功)
  - max_retries 耗尽抛 ValueError
  - few-shot 兼容性验证(RAG 调研场景不受影响)

### Phase 2:AuditLogHook 实现(半天)

- [x] 2.1 读 `hooks/base.py` 确认 `BaseHook` 接口
- [x] 2.2 实现 `hooks/builtin/audit_log.py`(AuditLogHook 类)
- [x] 2.3 写 `test_audit_event.py`(3 个测试):
  - subtask.completed → AgentEvent 写入且 sequence 递增
  - subtask.failed → AgentEvent 写入且 payload 含 error
  - 完整任务的事件流 sequence 连续无重复

### Phase 3:Executor 断点恢复(1 天)

- [x] 3.1 在 `executor.py` 的 `_persist_subtask_result()` 成功后同步写 `AgentSubTask` DB(status mapping: success→completed)
- [x] 3.2 新增 `resume_from_checkpoint(task_id)` 方法:
  - 加载 AgentTask + AgentSubTask
  - 重建 SharedContext(从 completed subtask 的 output)
  - 从 pending/running 的 subtask 继续
- [x] 3.3 新增 `pause()` 方法:更新 `AgentTask.status = "paused"`
- [x] 3.4 写 `test_multi_agent_resume.py`(5 个测试):
  - 全流程跑完 3 个 subtask,全部 completed,DB 持久化正确
  - 跑到第 2 个 subtask 时 kill,重启后从第 2 个续(第 1 个不重跑)
  - resume 后 SharedContext.artifacts 与原始一致
  - pause → resume 状态转换正确
  - 所有 subtask failed → resume 后仍 failed

### Phase 4:复杂任务 E2E(1 天)

- [x] 4.1 写 `test_multi_agent_complex.py`(2 个 E2E):
  - 传感器异常任务完整 E2E(Supervisor 分解 ≥ 3 SubTask)
  - 断言 Pipeline 顺序执行(researcher → analyst → writer)
  - 断言 SharedContext 跨步传递(analyst 能读到 researcher 的 anomalies)
  - 断言 final_synthesis 生成完整报告
  - 断言 AgentSubTask DB 全部 completed
  - 断点恢复 E2E:跑到第 2 个 subtask 时模拟 kill,resume 后产出一致

### Phase 5:文档 + 清理(半天)

- [x] 5.1 更新 `docs/technical/32-smart-assistant-multi-agent.md`:
  - 新增"§8 实战 demo:传感器异常分析报告"章节
  - 包含:任务分解示例、事件流示例、断点恢复操作指南、测试覆盖汇总
- [x] 5.2 本地验证:
  - 44 个 Plan 3 相关测试全绿
  - 无回归(原 16 个 executor 测试仍通过)

### Phase 6:PR + AI 检阅 + Merge(半天)

- [x] 6.1 建 feature 分支:`git switch -c feat/sa-multi-agent`
- [x] 6.2 推送到 origin + 创建 PR #87
- [ ] 6.3 等 CI 绿(运行中)
- [ ] 6.4 AI 检阅(运行中)
- [ ] 6.5 修复 HIGH/CRITICAL 问题
- [ ] 6.6 用户 merge PR
- [ ] 6.7 清理分支

---

## 5. 验收清单

- [ ] 复杂任务 E2E 全绿(无 mock 跑通,仅 sensor_tool 用 fixture 数据)
- [ ] 断点恢复 E2E 全绿
- [ ] AgentEvent 流可重放且状态一致
- [ ] pytest 覆盖率 ≥ 80%(smart_assistant 模块)
- [ ] CI 10/10 全绿(backend pytest + frontend jest + mypy + lint)
- [ ] AI 检阅无 CRITICAL/HIGH 问题
- [ ] `docs/technical/32-smart-assistant-multi-agent.md` 已更新"实战 demo"章节
- [ ] 用户验收:可在本地 5 分钟内复演传感器异常分析报告生成

---

## 6. 风险与缓解

| 风险 | 触发条件 | 缓解 |
|---|---|---|
| LLM 输出 JSON 不稳定 | few-shot 示例不够 | 增加 2-3 个不同场景的 few-shot,提高 temperature=0.3 → 0.2 |
| 断点恢复测试 flaky | 时序问题,DB 写入未完成就 kill | 用显式 `transaction.atomic()` + 等待 DB flush |
| E2E 跑超时(> 5min) | LLM 响应慢 | 设 `timeout_seconds=600`,测试中 mock LLMRouter 加速 |
| AgentEvent sequence 冲突 | 并发写入 | 用 `select_for_update()` 保护 sequence 自增 |

---

## 7. 不在本 Plan 范围

- ❌ Fan-out / Hierarchical 执行模式
- ❌ 前端 SSE 实时推送(Plan 4)
- ❌ Supervisor 动态介入 / 用户介入交互
- ❌ PIISanitizerHook / SensitiveDataGateHook / ToolTimeoutHook
- ❌ 新 LLM 接入(仅保留 Ollama)
- ❌ 性能优化(Plan 4)

---

## 8. 测试清单汇总

| 文件 | 测试数量 | 类型 |
|---|---|---|
| `test_supervisor_decomposition.py` | 4 | 单元 |
| `test_audit_event.py` | 3 | 单元 |
| `test_multi_agent_resume.py` | 5 | 单元 + 集成 |
| `test_multi_agent_complex.py` | 2 | 集成(E2E) |
| **合计** | **14** | - |

---

## 9. 推进顺序

```
[Plan 1 ✅] f8a01321 → [Plan 2 ✅] 91b2383b → [Plan 3 当前] → [Plan 4 待启动]
                                                        ↓
                                          feat/sa-multi-agent 分支
                                                        ↓
                                          PR #87 squash-merge → main
```

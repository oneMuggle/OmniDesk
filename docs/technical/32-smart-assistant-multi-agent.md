# 32. Smart Assistant 多 Agent 协作

> **状态**：✅ 已实现（v0.5.0，PR #32 — `feat/smart-assistant-multi-agent-collaboration`）
> **代码位置**：`omni_desk_backend/smart_assistant/agents/` + `omni_desk_backend/smart_assistant/hooks/`
> **里程碑 1.1–1.4 全部合入**：基础设施 → TaskPacket → MultiAgentExecutor → Supervisor + SSE

## 1. 设计动机

`smart_assistant` 原有单 Agent 管道（意图分类 → 工具链 → 回答）擅长**短任务单轮对话**，但**多步骤、多角色协作**的长任务（文献调研、数据分析、报告整理、代码开发）超出单 Agent 能力上限。

多 Agent 层在**不替换现有 `AgentOrchestrator`** 的前提下扩展：单轮聊天继续走原路径，长任务通过 `complex_task` 意图分流到 `MultiAgentExecutor`。

## 2. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    IntentClassifier                          │
│      (复杂任务识别 → 路由到 MultiAgentExecutor)                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  MultiAgentExecutor                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Supervisor LLM  →  任务分解为 SubTask DAG              │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Pipeline 模式：role(Researcher) → role(Analyst) → ...    │  │
│  │ Fanout 模式：3 个 researcher 并行                          │  │
│  │ Hierarchical：supervisor 动态调度                            │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 共享上下文：TaskPacket + SharedContext 跨 SubTask 传递     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Hook 系统（横向）                                │
│  - audit_log    ：所有 SubTask 写审计日志                       │
│  - pii_sanitizer：输入脱敏                                        │
│  - 其它策略钩子（pluggable）                                      │
└─────────────────────────────────────────────────────────────┘
```

## 3. 模块构成

| 文件 | 职责 |
|---|---|
| `agents/roles.py` | `AgentRole` 枚举 + `RoleProfile` 注册表（researcher / analyst / writer / coder / supervisor） |
| `agents/task_packet.py` | `TaskPacket` / `SubTask` 数据类，承载跨 Agent 任务数据 |
| `agents/shared_context.py` | `SharedContext`：跨 SubTask 共享上下文（tool 输出、变量、partial result） |
| `agents/executor.py` | `MultiAgentExecutor`：主执行器，编排 Pipeline / Fanout / Hierarchical |
| `agents/supervisor.py` | `Supervisor` LLM 任务分解 + 动态调整 |
| `agents/pipeline.py` *(内联在 executor 中)* | Pipeline 模式串行执行 |
| `quality_gate.py` *(内联)* | 质量门禁：基于 role 的 `output_contract` 校验 |
| `recovery.py` *(内联)* | Recovery Recipes：失败自愈 |
| `hooks/base.py` | `ToolHook` 协议 + `HookRegistry` |
| `hooks/builtin/audit_log.py` | 审计日志钩子 |
| `hooks/builtin/pii_sanitizer.py` | PII 脱敏钩子 |

## 4. 数据库模型

| 模型 | 字段要点 | 用途 |
|---|---|---|
| `AgentTask` | `user`, `status`, `intent`, `subtask_ids`, `final_result` | 用户提交的一次多 Agent 任务 |
| `AgentSubTask` | `task`, `role`, `status`, `output`, `error`, `started_at`, `finished_at` | 子任务实例 |
| `AgentEvent` | `task`, `type`, `payload`, `ts` | 事件流（用于回放 + UI 实时进度） |

## 5. API 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/smart-assistant/tasks/` | GET / POST | 列出 / 提交多 Agent 任务 |
| `/api/smart-assistant/tasks/{id}/` | GET | 任务详情（含 SubTask 状态） |
| `/api/smart-assistant/tasks/{id}/intervene/` | POST | 人工介入（取消 / 重试某 SubTask） |
| `/api/smart-assistant/tasks/{id}/events/` | GET (SSE) | 实时事件流 |
| `/api/smart-assistant/tasks/{id}/timeline/` | GET | 历史事件回放 |

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 是否引入 LangGraph / CrewAI | ❌ 自研 + 借鉴思想 | 依赖可控、调试可观测 |
| 与单 Agent 管道的关系 | 共存（非替换） | 复杂任务路由到 MultiAgentExecutor，简单对话继续快速通道 |
| 失败处理 | Recovery Recipes + 人工介入 | 关键任务不可静默吞错 |
| 质量门禁 | role × output_contract | 不同角色验证不同 output 形态 |
| 事件流 | SSE + 持久化 `AgentEvent` | 既能实时推送又能事后回放 |

## 7. 部署 / 运行

无需额外配置；多 Agent 任务使用项目同一 LLM 端点，与单 Agent 走同样的降级链：

- `REACT_APP_OLLAMA_ENDPOINT` 环境变量
- `llm_service` 降级链（Ollama → 远程 API → 兜底）
- Celery 异步任务 `execute_agent_task`

## 8. 实战 Demo:传感器异常分析报告(Plan 3 新增)

### 8.1 场景描述

**用户问句:** "分析本月所有传感器异常,生成根因报告 + 整改建议"

**Supervisor 分解输出:**
```json
{
  "objective": "分析本月传感器异常并生成根因报告",
  "execution_mode": "pipeline",
  "subtasks": [
    {
      "id": "researcher",
      "role": "researcher",
      "objective": "采集本月传感器异常数据",
      "inputs": {"query": "本月传感器异常记录"},
      "failure_mode": "retry",
      "depends_on": [],
      "quality_gate": ["anomalies 数量 >= 1"]
    },
    {
      "id": "analyst",
      "role": "analyst",
      "objective": "模式识别 + 异常归因",
      "inputs": {"anomalies": "$researcher.anomalies"},
      "failure_mode": "retry",
      "depends_on": ["researcher"],
      "quality_gate": ["root_causes 数量 >= 1"]
    }
  ],
  "final_synthesis": {
    "id": "writer",
    "role": "writer",
    "objective": "撰写根因报告 + 整改建议",
    "inputs": {
      "anomalies": "$researcher.anomalies",
      "root_causes": "$analyst.root_causes"
    },
    "depends_on": ["researcher", "analyst"]
  },
  "global_budget": 20000,
  "timeout_seconds": 600
}
```

### 8.2 执行流程

```
Supervisor(LLM 分解, few-shot 示例辅助)
    ↓
    ├─ SubTask 1: researcher
    │    工具: sensor_tool
    │    产出: anomalies: [{sensor_id, timestamp, severity}]
    │    → 持久化到 AgentSubTask DB(status=completed)
    │
    ├─ SubTask 2: analyst
    │    输入: $researcher.anomalies(SharedContext 自动注入)
    │    产出: root_causes: [{cause, frequency, impact}]
    │    → 持久化到 AgentSubTask DB
    │
    └─ SubTask 3: writer(final_synthesis)
         输入: $researcher.anomalies + $analyst.root_causes
         产出: 完整 Markdown 报告
         → 持久化到 AgentSubTask DB
```

### 8.3 断点恢复示例

**场景:** 执行到 analyst 时 worker 被 kill,researcher 已完成。

**恢复流程:**
```python
# 1. 从 DB 加载任务
result = MultiAgentExecutor.resume_from_checkpoint(
    task_id="xxx-xxx-xxx",
    llm_router=llm_router,
    tool_registry=tool_registry,
)

# 2. resume_from_checkpoint 内部:
#    - 加载 AgentTask + 已完成的 AgentSubTask
#    - 重建 SharedContext(从 completed subtask 的 output)
#    - 跳过 researcher(已完成),从 analyst 继续
#    - 继续执行 writer

# 3. 最终结果与无中断情况一致
assert result.status == "success"
```

### 8.4 审计回放

所有事件写入 `AgentEvent` 表,sequence 严格递增:
```
seq=1: task.started
seq=2: subtask.started(researcher)
seq=3: subtask.completed(researcher, tokens=100)
seq=4: subtask.started(analyst)
seq=5: subtask.completed(analyst, tokens=200)
seq=6: subtask.started(writer)
seq=7: subtask.completed(writer, tokens=300)
seq=8: task.completed(status=success, total_tokens=600)
```

可通过 `/api/smart-assistant/tasks/{id}/events/` API 获取完整事件流,用于:
- SSE 实时推送前端进度
- 故障排查(事件回放)
- 运营分析(成功率 / 平均耗时 / Token 消耗)

### 8.5 测试覆盖

| 测试文件 | 测试数量 | 覆盖点 |
|---|---|---|
| `test_supervisor_decomposition.py` | 5 | Supervisor 分解 + few-shot |
| `test_audit_event.py` | 3 | AuditLogHook 事件写入 |
| `test_multi_agent_resume.py` | 5 | 断点恢复 5 场景 |
| `test_multi_agent_complex.py` | 2 | 完整 E2E + resume E2E |
| **合计** | **15** | Plan 3 全部验收点 |

---

> 📅 最近更新:2026-07-17 — Plan 3 实战 demo 章节新增

## 9. 关联参考

- 设计灵感：`claw-code` (ultraworkers/claw-code) — Worker Boot / Task Packet / Recovery Recipes / Lane Event Sourcing
- 关联计划：`docs/plans/2026-06-21_multi-agent-collaboration.md`（**已归档，删档**）
- 上层架构：`docs/technical/16-smart-assistant.md` + `17-ai-assistant-deep-design.md`

---

> 📅 最近更新：2026-07-16 — 文档归档，从 docs/plans/2026-06-21_multi-agent-collaboration.md 提取。

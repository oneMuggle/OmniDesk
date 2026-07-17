# Smart Assistant 集成冲刺 设计规范

**日期:** 2026-07-17
**项目:** OmniDesk
**作者:** Claude
**状态:** 待用户审阅

---

## 1. 背景与目标

### 1.1 问题

OmniDesk `smart_assistant` 模块已具备 13+ 工具、6 个视图、3 级缓存、多 Agent 框架、RAGFlow 集成等能力,但在实际"串接业务功能"维度仍有缺口:

1. **端到端验证不足** — 现有工具单测齐全,但缺少"用户自然语言 → 智能助手路由 → 工具返回 → LLM 综合"的全链路 E2E 验收。
2. **多工具链尚未跑通真实场景** — `agent/tool_chain_planner.py` 和 `agent/tool_chain_executor.py` 已实现,但 plan 不可序列化、不支持嵌套变量引用、失败策略单一。
3. **多 Agent 协作缺真实任务** — `agents/MultiAgentExecutor` + `Supervisor` 已实现,但尚未在真实业务场景中跑通过完整 Pipeline。
4. **性能与 UX 体验有优化空间** — 流式 TTFB、Think 与正文视觉区分、取消按钮的可用性、缓存命中率均有待打磨。

### 1.2 目标

通过 **4 个独立 feature 分支(严格串行)** 完成 Smart Assistant 能力完整化:

| 分支 | 核心交付 | 验收 |
|---|---|---|
| `feat/sa-e2e-scenarios` | 5 个高频 E2E 场景 + 回答级缓存 + 演示脚本 | 5 场景可演示 + 测试 ≥ 80% |
| `feat/sa-multi-tool-chain` | 工具链规划器升级 + 3 个跨工具场景 | LLM plan 可序列化、3 场景可演示 |
| `feat/sa-multi-agent` | 1 个复杂任务(异常分析报告)真实跑通 + 断点恢复 | 任务可中断 + 恢复 |
| `feat/sa-perf-ux` | 后端性能 + 前端 UX | P95 < 1.5s、LCP < 2.5s |

### 1.3 范围(明确做与不做)

| 做 | 不做 |
|---|---|
| 5 个高频场景端到端验证(排班/人员/知识库/公告/合规) | 升级 Django 4.2 → 5.x |
| 3 个跨工具链场景(排班→报告→公告 等) | 升级 React 18 → 19 |
| 1 个复杂多 Agent 任务(异常分析报告) | 接入新 LLM(仅保留 Ollama) |
| 后端性能优化(缓存、并行工具调用、连接复用) | 移动端原生 App |
| 前端 UX 优化(打字机、Think 分离、取消按钮) | 多语言(仅保留中文) |
| 文档同步(用户手册新增 5 场景章节) | 写操作(代用户创建排班/预约) |
| 测试覆盖率维持 ≥ 80% | 主动推送(每天早上推送) |

### 1.4 演示场景(精选 5 个高频)

| 场景 | 工具 | 自然语言问句样例 |
|---|---|---|
| 排班查询 | `ScheduleTool` | "张三这周值班是几号?" |
| 人员查询 | `PersonnelTool` | "帮我找开发部的李四" |
| 知识库问答 | `RAGTool` | "公司的 VPN 怎么登录?" |
| 公告查询 | `AnnouncementTool` | "这周有什么公告?" |
| 合规检查 | `ComplianceTool` | "张三还有几条待整改?" |

---

## 2. 设计方案

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       Frontend (React 18 + Ant Design 5)                 │
│  SmartChatPage / QuickAssistant / 流式打字机 / Think 分离 / 取消按钮    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ POST /api/smart-assistant/chat/stream/
                                   │ SSE 协议(AbortController 可取消)
                                   ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                       Backend (Django + DRF)                              │
│                                                                          │
│  ChatView ─→ 限流(30/min) ─→ 缓存查询(2h TTL) ─→ [HIT 短路推 SSE]      │
│                                          ↓ MISS                           │
│                              IntentClassifier(Ollama + 关键词 fallback)  │
│                                          ↓                                │
│                              ToolChainPlanner(LLM 生成 plan)              │
│                                          ↓                                │
│                              PlanValidator(工具/权限/依赖校验)            │
│                                          ↓                                │
│                              ToolChainExecutor                            │
│                                ├── asyncio.gather(无依赖并行)             │
│                                ├── 每步构造 ToolContext(user, request_id) │
│                                ├── 每步 Tool.execute(query, ctx)         │
│                                └── 每步 AgentLog(工具/输入/输出/延迟)    │
│                                          ↓                                │
│                              ResultSynthesizer(LLM 综合)                  │
│                                          ↓                                │
│                              缓存写入 + SSE 推送 meta → chunks → done    │
└──────────────────────────────────────────────────────────────────────────┘
                                   ↓
                    ┌──────────────────────────────────────────────┐
                    │              Frontend 渲染                    │
                    │  打字机 + Think 分离 + 工具卡片 + 取消按钮   │
                    └──────────────────────────────────────────────┘
```

### 2.2 数据契约

#### ToolContext

```python
@dataclass(frozen=True)
class ToolContext:
    user: CustomUser           # 必填,工具按 user 权限过滤
    request_id: str            # UUID,关联日志
    history: list[dict]        # 多轮对话历史
    plan_id: Optional[str]     # 多工具链场景的 plan 标识
```

#### SSE Event 协议

```typescript
type SSEEvent =
  | { type: 'meta'; request_id: string; intent: string; tools: string[] }
  | { type: 'chunk'; content: string; ts: number }
  | { type: 'tool_call'; name: string; input: any; output: any; latency_ms: number }
  | { type: 'think'; content: string }
  | { type: 'error'; code: string; message: string; recoverable: boolean }
  | { type: 'done'; total_latency_ms: number; cache_hit: boolean };
```

#### 缓存键

```
cache_key = sha256(f"{query}|{user_id}|{cache_version}|{intent_type}")
ttl = 2h(回答级) / 30min(工具级) / 1h(意图级)
```

### 2.3 分支 1:`feat/sa-e2e-scenarios`(2-3 天)

#### 5 个高频 E2E 场景

| 场景 | 工具 | 验证点 |
|---|---|---|
| 排班查询 | `ScheduleTool` | 日期解析 + 权限过滤 + 中文姓名匹配 |
| 人员查询 | `PersonnelTool` | 部门过滤 + 脱敏(只返回公开字段) |
| 知识库问答 | `RAGTool` | RAGFlow 检索 + 引用来源 + 缓存命中 |
| 公告查询 | `AnnouncementTool` | 时间窗口过滤 + 按权限返回 Post 列表 |
| 合规检查 | `ComplianceTool` | ComplianceIssue 状态过滤 + 部门范围 |

#### 涉及文件

| 类别 | 文件 | 动作 |
|---|---|---|
| 新增 | `omni_desk_backend/smart_assistant/tests/test_e2e_5_scenarios.py` | 5 个 E2E 场景 |
| 新增 | `omni_desk_frontend/src/features/smart-assistant/demo/e2e-script.md` | 演示脚本 |
| 新增 | `docs/user-manual/05-smart-assistant-scenarios.md` | 用户手册 |
| 修改 | `omni_desk_backend/smart_assistant/cache.py` | 新增回答级缓存(2h) |
| 修改 | `omni_desk_backend/smart_assistant/views/chat.py` | 缓存命中短路 |
| 新增 | `omni_desk_backend/smart_assistant/tests/test_cache.py` | 5 个缓存测试 |

#### 验收清单

- 5 个 E2E 全绿
- pytest 总覆盖率 ≥ 80%
- 演示脚本可在本地 30 秒内复演
- 缓存命中 P95 < 200ms

### 2.4 分支 2:`feat/sa-multi-tool-chain`(3-4 天)

#### 3 个跨工具链场景

- **场景 A**:排班 → 报告 → 公告("帮我查张三这周值班,生成排班报告,发到运维群公告")
- **场景 B**:传感器异常 → 责任人 → 周报("分析本月异常传感器,列出责任人,生成周报")
- **场景 C**:合规 → 项目 → 风险评估("查找近期合规问题,关联到具体项目,给出风险评估")

#### 升级点

| 升级点 | 现状 | 目标 |
|---|---|---|
| Plan 序列化 | 内存对象 | JSON + DB 持久化(可恢复) |
| `$variable` 替换 | 仅字符串模板 | 支持嵌套引用 `{{step1.output.users[0].id}}` |
| 失败处理 | 单步失败即终止 | 支持 `on_failure: skip\|retry\|fallback` |
| 可观测性 | 无 | 每步写入 `AgentLog` |

#### 涉及文件

| 文件 | 动作 |
|---|---|
| `agent/tool_chain_planner.py` | 升级:plan 输出 JSON schema,带 `on_failure` 字段 |
| `agent/tool_chain_executor.py` | 升级:嵌套 `$variable`、失败策略、step-level 日志 |
| `agent/plan_serializer.py` | 新增:`Plan.to_dict()` / `Plan.from_dict()` / DB 模型 |
| `models.py` | 新增:`ToolChainPlan` 表 |
| `tests/test_multi_tool_chain.py` | 3 个跨工具场景 + 失败策略测试 |

#### 验收清单

- 3 个跨工具场景 E2E 全绿
- plan 可序列化/反序列化(往返不丢字段)
- 失败策略 3 种全部覆盖(skip/retry/fallback)
- 每步 AgentLog 完整

### 2.5 分支 3:`feat/sa-multi-agent`(3-4 天)

#### Demo 任务

"分析本月所有传感器异常,生成根因报告 + 整改建议"

#### Agent 角色协作

```
Supervisor(LLM 分解任务)
    ↓
    ┌─ Researcher(Sensor 数据采集)─┐
    ├─ Analyst(模式识别 + 异常归因)─├→ SharedContext
    └─ Writer(报告 + 整改建议)─────┘
```

#### 关键能力点

| 能力 | 实现位置 | 验证手段 |
|---|---|---|
| 任务分解 | `agents/supervisor.py` | 断言生成 ≥ 3 个 SubTask |
| Pipeline 模式串行 | `agents/executor.py` | 顺序断言 |
| SharedContext 跨步传递 | `agents/shared_context.py` | analyst 能读到 researcher 输出 |
| 审计回放 | `hooks/builtin/audit_log.py` + `AgentEvent` | 重放事件流,状态一致 |
| 断点恢复 | `AgentTask.status` + `subtask_ids` | kill worker → 重启 → 续 |

#### 涉及文件

| 文件 | 动作 |
|---|---|
| `agents/supervisor.py` | 升级:分解 prompt 加 few-shot 示例 |
| `agents/executor.py` | 升级:断点恢复逻辑 |
| `hooks/builtin/audit_log.py` | 升级:写入 `AgentEvent` |
| `tests/test_multi_agent_complex.py` | 1 个复杂任务 E2E + 断点恢复 E2E |
| `docs/technical/32-smart-assistant-multi-agent.md` | 补"实战 demo"章节 |

#### 验收清单

- 复杂任务 E2E 全绿(无 mock 跑通)
- 断点恢复 E2E 全绿
- AgentEvent 流可重放且状态一致

### 2.6 分支 4:`feat/sa-perf-ux`(2-3 天)

#### 性能目标

| 指标 | 当前 | 目标 | 手段 |
|---|---|---|---|
| 非流式 P95 | ~3s | < 1.5s | 缓存命中短路 + 工具并行 |
| 流式 TTFB | ~800ms | < 300ms | 缓存 + 跳过不必要工具 |
| RAG 检索延迟 | ~1s | < 500ms | Ragflow 连接复用 |
| 前端 LCP | 未知 | < 2.5s | 已有 chunk 拆分 + UX 优化 |

#### 涉及文件

**后端:**

| 文件 | 改动 |
|---|---|
| `agent/orchestrator.py` | 工具调用改为 `asyncio.gather` 并行(无依赖时) |
| `cache.py` | 缓存键加 `cache_version`,支持工具版本失效 |
| `ragflow_service/client.py` | 长连接复用(`requests.Session`) |

**前端:**

| 文件 | 改动 |
|---|---|
| `SmartChatPage.jsx` | 流式打字机效果(每 chunk 50ms 节流) |
| `ThinkContent.jsx` | Think 与正文视觉区分(色块 + 图标 + 默认折叠) |
| `SmartChatPage.jsx` | 取消按钮(AbortController) + 取消后状态清理 |
| `ToolResult.jsx` | 卡片复制按钮 + Markdown 复制 |

#### 验收清单

- 后端 P95 < 1.5s(非流式)/ < 300ms(流式首字节)
- 前端 LCP < 2.5s
- 50 并发请求零失败
- 取消按钮 100% 可用

---

## 3. 错误处理

### 3.1 错误处理矩阵

| 失败点 | 错误级别 | 用户提示 | 内部动作 | 是否降级 |
|---|---|---|---|---|
| Ollama 不可达 | LOW | "智能助手暂不可用,请稍后重试" | 关键词 fallback | ✅ |
| 工具执行抛异常 | MEDIUM | "查询 X 失败,已自动跳过" | AgentLog 记录 stack | ✅ |
| 工具返回空 | LOW | "未找到 X 相关数据" | 正常返回 | ✅ |
| LLM 生成超时(>10s) | MEDIUM | "回答生成超时,已截断" | 终止流 | ⚠️ |
| 权限不足 | HIGH | "您没有权限查询 X" | 立即终止,审计 | ❌ |
| 客户端断开 | LOW | (前端静默) | 终止 LLM stream | ⚠️ |
| 缓存击穿 | MEDIUM | (正常返回) | 单飞锁 | ✅ |
| Plan 校验失败 | HIGH | "任务规划失败,请换种说法" | AgentLog 记录 | ❌ |
| 多 Agent SubTask 失败 | HIGH | "任务 X 执行失败,已恢复/需人工" | Recovery Recipe | ⚠️ |

### 3.2 用户提示文案统一规范

| 错误码 | 文案 | 前端展示 |
|---|---|---|
| `INTENT_UNCLEAR` | "没理解您的意图,试试这样问:..." | 弹层 + 3 个示例问句 |
| `TOOL_TIMEOUT` | "查询 X 超时,已跳过" | 内联提示 |
| `PERMISSION_DENIED` | "您没有权限查询 X" | 内联提示 |
| `LLM_DOWN` | "智能助手暂不可用" | 顶部 Banner |
| `PLAN_INVALID` | "任务太复杂,无法自动完成" | 弹层 + 建议拆分 |

### 3.3 日志与可观测

| 事件 | 日志级别 | 字段 |
|---|---|---|
| 用户提问 | INFO | user_id, query_hash, intent |
| 意图分类 | INFO | intent, classifier_used |
| 工具调用 | INFO | tool_name, latency_ms, status |
| LLM 调用 | INFO | model, prompt_tokens, completion_tokens, latency_ms |
| 缓存命中 | DEBUG | cache_key, ttl_remaining |
| 错误 | WARNING/ERROR | error_code, stack, recoverable |
| 客户端断开 | DEBUG | request_id, partial_chunks |

---

## 4. 测试策略

### 4.1 测试金字塔

```
                          ┌─────────────┐
                          │  E2E (5+3+2)│
                          ├─────────────┤
                          │ 集成 (30+)  │
                       ┌──┴─────────────┴──┐
                       │  单元 (200+ 新增) │
                       └───────────────────┘
```

### 4.2 各分支测试清单

#### 分支 1

- 单元:15 个(`test_cache.py` 5 + `test_intent_fallback.py` 4 + `test_tool_context.py` 6)
- 集成:5 个 E2E 场景
- 性能:P95 < 200ms(缓存命中)

#### 分支 2

- 单元:20 个(`test_plan_serializer.py` 8 + `test_tool_chain_executor.py` 6 + `test_plan_validator.py` 6)
- 集成:5 个(3 场景 + skip 策略 + retry 策略)

#### 分支 3

- 单元:12 个(`test_supervisor_decomposition.py` 4 + `test_multi_agent_resume.py` 5 + `test_audit_event.py` 3)
- 集成:2 个(复杂任务 E2E + 断点恢复 E2E)

#### 分支 4

- 性能:10 个(`test_perf_chat.py` 5 + `test_ragflow_perf.py` 3 + `test_cache_stampede.py` 2)
- 前端 UX:手动验收 + Lighthouse 跑分

### 4.3 整体验收标准(4 个分支全合入后)

| 维度 | 指标 | 目标 |
|---|---|---|
| **可演示** | 5 个高频场景可手动复演 | ✅ |
| | 3 个跨工具链场景可手动复演 | ✅ |
| | 1 个多 Agent 复杂任务可手动复演 | ✅ |
| **测试** | pytest 总覆盖率 | ≥ 80% |
| | E2E 场景数 | ≥ 10(5 高频 + 3 跨工具 + 2 多 Agent) |
| | 性能测试 | ≥ 10 个 |
| **性能** | 后端 P95(非流式) | < 1.5s |
| | 流式 TTFB | < 300ms |
| | 前端 LCP | < 2.5s |
| **质量** | CI 全绿 | ✅ |
| | 文档与代码同步 | ✅ |
| | 无 CRITICAL/HIGH 代码审查问题 | ✅ |

---

## 5. 风险与回滚策略

| 风险 | 触发条件 | 回滚手段 |
|---|---|---|
| 缓存引入一致性问题 | 工具返回错误但缓存命中 | 加 `cache_version`,工具更新时手动失效 |
| LLM 编排不稳定 | E2E flaky 率 > 10% | 改用 mock_llm_router 兜底,留真链路为可选 |
| 多 Agent 任务跑超时 | 任务 > 5min | 设置 timeout + Recovery Recipe |
| 性能优化引入 bug | 并行调用顺序错乱 | 加顺序断言 + 单独跑回归 |

---

## 6. 推进顺序(严格串行)

```
[1: feat/sa-e2e-scenarios]    ──→ PR #N1 merge ──→
                                          ↓
[2: feat/sa-multi-tool-chain] ──→ PR #N2 merge ──→
                                          ↓
[3: feat/sa-multi-agent]      ──→ PR #N3 merge ──→
                                          ↓
[4: feat/sa-perf-ux]          ──→ PR #N4 merge ──→
```

每个分支:
1. 从最新 main 切出 → 编码 → 调试通过 → 跑本地验证
2. 推 feature 分支到 origin → 创建 PR
3. CI 绿 → AI 检阅 → 用户 merge PR
4. 合并后清理分支,再切下一个分支

---

## 7. 不在本设计范围

- 升级 Django 4.2 → 5.x(单独立项,涉及依赖兼容)
- 升级 React 18 → 19(同上)
- 接入新 LLM(Ollama 以外,需要业务侧决定)
- 移动端原生 App
- 多语言(仅保留中文)
- 写操作(代用户创建排班/预约)
- 主动推送(每天早上推送今日安排)

---

## 8. 参考资料

- `docs/technical/16-smart-assistant.md` — 智能助手系统总览
- `docs/technical/17-ai-assistant-deep-design.md` — AI 助手深度设计
- `docs/technical/32-smart-assistant-multi-agent.md` — 多 Agent 协作
- `docs/technical/33-ragflow-integration.md` — RAGFlow 集成
- `docs/superpowers/specs/2026-07-07-smart-assistant-cross-module-aggregation-design.md` — 跨模块汇总(参考前例)
- `docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md` — 阶段 3 新工具(ToolContext 已引入)
- `docs/plans/2026-06-21_smart-assistant-display-optimization.md` — 显示优化(部分已完成)
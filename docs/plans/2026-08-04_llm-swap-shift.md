# 智能助手接入换班流程（LLM 换班工具）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-08-04 |
| 作者 | Claude（人工指令触发） |
| 状态 | ⏳ 草案，待用户审批（2026-08-04 用户确认核心决策 1/2/3 后进入 Phase 1） |
| 涉及版本 | v0.6.x（main 分支 alpha 通道） |
| 关联后端 | `smart_assistant` + `events` |
| 关联前端 | `features/schedule` + `shared/components/QuickAssistant.jsx` |

---

## 1. 背景与目标

### 1.1 现状

| 层 | 现状 |
|---|---|
| 业务层（`events`） | ✅ `ScheduleSwapRequest` 模型 + `SwapRequestViewSet` 已实现完整 CRUD 与状态机（pending → approved/rejected/cancelled/expired） |
| 前端 UI（`features/schedule`） | ✅ 用户已可手动建换班申请、对方 accept/reject、撤销 |
| 智能助手层（`smart_assistant`） | ❌ **未接入**：`tools/` 下仅有只读 `schedule_tool.py`，无任何写换班工具；`prompt_builder.py` 与 `tool_chain_planner.py` 关键词表均未覆盖"换班/替班/调班"；`QuickAssistant.jsx` 无快捷入口 |

### 1.2 痛点

当用户在 `QuickAssistant` 输入"我想和李四换一下周三的班"，智能助手只能返回值班人列表，**无法**真正发起 `ScheduleSwapRequest`。用户被迫：记住 swap 申请页面路径 → 找到目标日期排班 → 选择接收方 → 填理由 → 提交。

### 1.3 目标

让用户通过自然语言一句话完成 **"查询本人排班 → 解析接收方 → 解析换班日期 → 创建换班申请 → 二次确认 → 返回申请 ID"** 全链路；接收方也可在 QuickAssistant 用自然语言主动决策（"同意李四的换班"），但**接收方必须亲自发起**决策指令，LLM 不得在用户没说话时自动操作。

### 1.4 非目标 / 后续

- ✅ **允许接收方**通过 LLM 对话**主动**查询 + accept / reject / cancel（接收方自己说"同意李四的换班"才算合规，**不**是 LLM 代签）
- ❌ **不**让 LLM 在用户**没发起** accept/reject 指令时自动决策（避免静默代签）
- ❌ **不**让 LLM 替**第三方**对接收方的换班申请决策
- ❌ 不改 `ScheduleSwapRequest` 模型字段或状态机
- ❌ 不动 `events/views/swap.py` 既有逻辑
- ❌ 不做语音输入、批量换班、跨月份调度

---

## 2. 涉及的文件与模块

### 2.1 后端新增

| 文件 | 类型 | 用途 |
|---|---|---|
| `omni_desk_backend/smart_assistant/tools/swap_request_tool.py` | 新增 | 三个工具类：`SwapRequestCreateTool`（write, 创建）+ `SwapRequestDecideTool`（write, 接收方决策）+ `SwapRequestQueryTool`（read, 查询） |
| `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py` | 新增 | 单元测试，三个工具全覆盖，≥ 80% 覆盖 |
| `omni_desk_backend/smart_assistant/tools/__init__.py` | 修改 | 显式 import + register 三个新工具 |
| `omni_desk_backend/smart_assistant/agent/prompt_builder.py` | 修改 | `INTENT_PROMPT` 新增 swap_request_create / swap_request_decide / swap_request_query 三个分支 |
| `omni_desk_backend/smart_assistant/agent/tool_chain_planner.py` | 修改 | `intent_keywords` 增"换班/替班/调班/同意换班/拒绝换班/收到的换班"等映射 |

### 2.2 后端可选（视前端方案决定）

| 文件 | 用途 |
|---|---|
| `omni_desk_backend/smart_assistant/views.py` | 在 `/api/smart-assistant/...` 路由里把"待确认"信号透传给前端（参考既有 `confirmation_required` 错误码） |
| `omni_desk_backend/smart_assistant/hooks/builtin/audit_log.py` | 新增 `SwapAuditHook`，写 `ScheduleSwapAuditLog`（同 swap-requests ViewSet 的审计模式） |

### 2.3 前端

| 文件 | 修改 |
|---|---|
| `omni_desk_frontend/src/shared/components/QuickAssistant.jsx` | 解析工具返回中的 `confirmation_required` 信号 → 弹确认卡（Ant Design `Modal.confirm`），列出发起人/接收方/日期/理由，确认后 replay |
| `omni_desk_frontend/src/features/schedule/api/swapApi.ts` | 复用 `swap-requests` REST API，无新增 |

### 2.4 文档

| 文件 | 操作 |
|---|---|
| `docs/technical/16-smart-assistant.md`（或最近章节） | 功能完成后追加"换班工具"小节，列出 schema、关键词、风险等级 |
| `docs/user-manual/06-smart-assistant-quickstart.md` | 增加示例：自然语言发起换班 + 二次确认截图 |

---

## 3. 技术方案

### 3.1 工具设计

#### 3.1.1 `SwapRequestCreateTool`（写，risk_level=write，require_confirmation=True）

仅**申请方**调用：发起换班申请。等二次确认后真正落库。

```python
class SwapRequestCreateTool(BaseTool):
    name = "swap_request_create"
    description = "基于自然语言发起换班/替班申请（接收方决策后生效）"
    intent_type = "swap_request_create"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query, context):
        """输入:用户原文。输出:待确认 swap 草稿 / 创建结果。"""
        # 1. 解析:从 query 抽取 target_personnel_name、target_date(scope=当周/下周/具体日期)
        # 2. 校验:context.user 必须是某个未来 original_schedule 的 duty_person 或 duty_leader
        # 3. 落库:复用 events.SwapRequestViewSet.perform_create 业务规则
        # 4. 返回:{"found": True, "swap_id": int, "draft": {...}, "awaiting_target": true}
```

参数抽取策略（**LLM 抽取 + Python 校验**双保险）：
- **LLM 阶段**：`tool_chain_planner` 解析出 `{target_name, date_phrase, reason?}`
- **Python 阶段**：用 `Personnel.objects.filter(name__icontains=target_name)` 严格校验；多匹配返回 409 让 LLM 澄清；date_phrase 用 `dateparser` 解析（已存在的依赖，见 `requirements-prod.txt`）
- **失败兜底**：LLM 解析不出 target_name 或 date_phrase 时，返回 `{"found": False, "needs_clarification": ["目标同事姓名？", "换哪天的班？"]}`，让 LLM 追问用户

#### 3.1.2 `SwapRequestDecideTool`（写，risk_level=write，require_confirmation=True）

仅**接收方**调用：对收到的换班申请主动 accept / reject / cancel。

```python
class SwapRequestDecideTool(BaseTool):
    name = "swap_request_decide"
    description = "对收到的换班申请做出决策（accept/reject/cancel）"
    intent_type = "swap_request_decide"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query, context):
        """输入:用户原文。输出:草稿 + 待二次确认。"""
        # 1. 解析:decision ∈ {accept, reject, cancel}, target_swap_id? 或 requester_name + date?
        # 2. 校验:context.user.personnel 必须是 swap 的 target_personnel(accept/reject)
        #    或 requester(cancel)
        # 3. 落库:复用 SwapRequestViewSet.accept / reject / cancel
```

合规要点：
- LLM **必须**先在 `SwapRequestQueryTool` 拿到具体 swap_id + 申请人 + 日期，让用户确认是哪一个申请
- 仅当用户**显式**说出 accept / reject / cancel 时才进入本工具；闲聊语境不触发
- 二次确认卡强制展示"你将对 XX 的换班申请执行 同意/拒绝"——防误点
- 同一申请 5 秒内不允许重复决策（防 race）

#### 3.1.3 `SwapRequestQueryTool`（读，risk_level=read）

查询当前用户发起的 + 接收的换班申请状态，关键词："我发起的换班 / 我收到的换班 / 换班进度 / 收到的换班申请"。

```python
class SwapRequestQueryTool(BaseTool):
    name = "swap_request_query"
    description = "查询换班申请状态（我发起的 / 我收到的）"
    intent_type = "swap_request_query"
    risk_level = "read"
```

### 3.2 二次确认流程

```
用户: "我想和李四换一下周三的班"
        │
        ▼
[LLM] 意图分类 → swap_request_create
        │
        ▼
[SwapRequestCreateTool.execute]
   解析 + 校验 + 落库 → 拿到 swap_id
        │
        ▼
[执行器] 检测到 require_confirmation=True
   → 返回 {"awaiting_confirmation": True, "draft": {...}}
        │
        ▼
[前端 QuickAssistant] 弹确认卡:
   "将为以下换班申请发起请求,确认吗?
    发起人:张三(您)
    接收方:李四
    原排班:2026-08-06(周三)
    理由:—"
   [确认]  [取消]
        │
        ▼ (用户点确认)
[前端] 调 /api/smart-assistant/.../confirm swap_id
[后端] 真正执行 perform_create(已存在)
[返回] swap_id + 状态
```

### 3.3 关键词映射（修改 `tool_chain_planner.py`）

```python
intent_keywords = {
    # ... 既有 ...
    "swap_request_create": ["换班", "替班", "调班", "换一下", "替一下", "和.*换", "跟.*换"],
    "swap_request_decide": ["同意换班", "拒绝换班", "撤销换班", "取消换班",
                            "接受换班", "不同意换班", "准了", "驳回换班"],
    "swap_request_query":   ["我发起的换班", "换班进度", "换班状态", "收到的换班",
                            "收到的换班申请", "谁要跟我换班"],
}
```

注意：避免和"调换座位/换设备"等无关场景冲突——`swap_request_create` / `swap_request_decide` 均需由 Python 校验兜底（必须找到具体 personnel/swap 记录，否则拒绝）。

### 3.4 权限与审计

- **权限**：`SwapRequestCreateTool` 仅允许 `context.user.personnel` 关联到未来 `Schedule.duty_person` 或 `duty_leader`；与 `SwapRequestViewSet.perform_create` 一致
- **审计**：复用 `ScheduleSwapAuditLog`，写入 `actor=user, action="create_via_llm"`
- **速率**：写工具加 60s 滑动窗口，每用户每分钟最多 **10 次**（用户决策，2026-08-04；覆盖 create + decide 全部写操作），防误触发/刷量，配置在 `settings.SMART_ASSISTANT_WRITE_RATE_LIMIT`

### 3.5 错误码契约

| 场景 | 返回 | LLM 行为 |
|---|---|---|
| 解析不出 target_name | `{"found": False, "needs_clarification": ["目标同事姓名？"]}` | 追问 |
| 解析不出 date | `{"found": False, "needs_clarification": ["换哪天的班？"]}` | 追问 |
| 目标 Personnel 不存在 | `{"found": False, "reason": "未找到同事'李五'"}` | 提示姓名错误 |
| 目标 Personnel 未关联未来排班 | `{"found": False, "reason": "该同事未来 14 天无排班,无法对调"}` | 提示对调范围限制 |
| 用户本人无未来排班 | `{"found": False, "reason": "您未来 14 天无排班,无法发起换班"}` | 提示 |
| 已存在 pending 申请 | `{"found": False, "reason": "您已发起过该日期换班申请,申请号 #123"}` | 引导查询 |
| 用户取消确认 | `{"found": False, "cancelled": True}` | 终止 |

---

## 4. 实施步骤

> 每个步骤完成后跑 `pytest --ds=omni_desk_backend.settings.test` 与 `npm run lint`，再勾选。
> **Phase 1 必须先通过框架验证闸门**（步骤 1.0），确认 `require_confirmation` 流程可端到端跑通后再进入业务开发。

### Phase 1：基础（独立交付）

- [ ] **步骤 1.0 框架验证闸门（先决条件）**：写一个最小 `ping_tool`（read 等级，`require_confirmation=False`）和一个最小 `echo_write_tool`（write 等级，`require_confirmation=True`），手动驱动一次完整链路：
   1. ping_tool execute → 直接返回
   2. echo_write_tool execute → 返回 `awaiting_confirmation` 信号
   3. 前端 QuickAssistant mock 收到信号 → 弹 Modal.confirm
   4. 用户点确认 → 后端 replay execute → 返回最终结果
   
   **验证目标**：确认 `BaseTool.require_confirmation` 在现有 orchestrator 中是否能完整跑通"execute → reject(confirm) → replay → success"流程。
   - ✅ 跑通 → 进入步骤 1.1
   - ❌ 跑不通 → **暂停**，优先补 orchestrator 的 confirm-replay 流程，单独建 `feat/sa-confirm-framework` 子任务完成后再回来
- [ ] **步骤 1.1**：创建 `swap_request_tool.py` 骨架（三个类，继承 `BaseTool`，声明 `risk_level`、`require_confirmation`、`intent_type`）
- [ ] **步骤 1.2**：在 `tools/__init__.py` 显式 import 并通过 `ToolRegistry.register()` 注册三个工具
- [ ] **步骤 1.3**：写最小单元测试 `test_swap_request_tool.py`：mock `context.user`，验证 `SwapRequestQueryTool` 仅返回当前用户相关记录
- [ ] **步骤 1.4**：跑 `pytest -k swap_request_tool`，覆盖率 ≥ 80%

### Phase 2：意图与规划

- [ ] **步骤 2.1**：修改 `prompt_builder.py` 的 `INTENT_PROMPT`，增 swap_request_create / swap_request_decide / swap_request_query 三个分支
- [ ] **步骤 2.2**：修改 `tool_chain_planner.py` 的 `intent_keywords`，加 12 个关键词（create 7 个 + decide 8 个 + query 6 个，详见 §3.3）；用 `tests/test_tool_chain_planner_coverage.py` 加单元测试覆盖
- [ ] **步骤 2.3**：跑意图识别端到端：`pytest -k intent_classifier` 验证
   - "我想和李四换班" → `swap_request_create`
   - "同意张三的换班" → `swap_request_decide`
   - "我收到的换班" → `swap_request_query`

### Phase 3：写工具核心

- [ ] **步骤 3.1**：`SwapRequestCreateTool.execute` 实现：解析 query（正则 + 简单 NLP）、查 Personnel、校验未来排班、生成 draft 返回（**不**真正落库，等二次确认）
- [ ] **步骤 3.2**：集成 `dateparser`（如未安装，加进 `requirements.in`）；测试用例覆盖"明天/后天/下周三/8月6日/X月X日"5 种日期表达
- [ ] **步骤 3.3**：补充步骤 1.3 的测试：创建申请时多姓名匹配返回 needs_clarification、不存在姓名返回 reason、未来 14 天过滤
- [ ] **步骤 3.4**：审计日志：`SwapAuditHook`（如 Phase 1 暂未做）/或工具 execute 内直接写 `ScheduleSwapAuditLog`

### Phase 4：二次确认 + 前端集成

- [ ] **步骤 4.1**：后端：`SwapRequestCreateTool` 在确认回调路径（新增 `confirm_swap` 方法，或复用 ViewSet）真正调 `perform_create` 业务逻辑
- [ ] **步骤 4.2**：前端 `QuickAssistant.jsx`：解析 `awaiting_confirmation` 信号 → 弹 `Modal.confirm`，列出 draft 字段
- [ ] **步骤 4.3**：前端：用户点确认后调后端确认接口；点取消返回 `cancelled` 信号
- [ ] **步骤 4.4**：前端 E2E（vitest + jsdom 或 Playwright）：模拟 "我想和 XX 换班" → 弹窗 → 确认 → 看到 swap_id

### Phase 5：风控与文档

- [ ] **步骤 5.1**：速率限制：smart_assistant middleware 加 `SWAP_WRITE_RATE_LIMIT`（默认每分钟 3 次）；超限返回 429
- [ ] **步骤 5.2**：CHANGELOG.md 加条目（feat: 智能助手接入换班申请）
- [ ] **步骤 5.3**：`docs/technical/...` 增"换班工具"小节
- [ ] **步骤 5.4**：`docs/user-manual/...` 增示例对话与截图
- [ ] **步骤 5.5**：合并到 `docs/plans/` 归档（按 `feature-development.md` 规范：完成 → 技术手册 → **删除 plans 副本**）

### Phase 6：CI 与合并

- [ ] **步骤 6.1**：本地跑完整 `pytest` + `npm run test:coverage`，覆盖率 ≥ 80%
- [ ] **步骤 6.2**：建 `feat/sa-swap-shift` 分支，按 `feature-branch-workflow.md` 走 PR + CI
- [ ] **步骤 6.3**：CI 绿后合并到 main，按 `branch-and-release-strategy.md` 走 alpha 通道

---

## 5. 风险评估与依赖

### 5.1 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| LLM 误识别"调换座位/换设备"为换班 | 中 | Python 端校验：必须找到未来排班，否则拒绝 |
| 用户姓名重复导致误换班对象 | 高 | 校验链：Personnel 唯一性 + 未来排班存在性 + 二次确认对话框强制展示目标姓名 |
| 写工具被滥用（误触发/刷量） | 中 | 速率限制每用户每分钟 3 次 + 二次确认必须用户点确认 |
| 接收方被越权代签 | 中 | LLM 不替第三方决策；接收方决策必须本人发起指令 + 二次确认；同一 swap 5 秒内不可重复决策 |
| 同一用户刷量 | 中 | 速率限制每用户每分钟 10 次（写工具总和），超限返回 429 |
| 测试覆盖不足导致回归 | 中 | Phase 6.1 强制覆盖率 ≥ 80%，未达标打回 |
| Windows 7 / 老浏览器前端 Modal 兼容 | 低 | 复用既有 Ant Design Modal，兼容性已验证 |

### 5.2 依赖

| 依赖 | 状态 |
|---|---|
| `dateparser` | ⚠️ 待确认 `requirements-prod.txt` 是否已含；如无则加入 `requirements.in` 并 `pip-compile` |
| `events.ScheduleSwapRequest` 模型 | ✅ 已有 |
| `events.SwapRequestViewSet.perform_create` 业务逻辑 | ✅ 已有，工具直接复用 |
| `BaseTool.require_confirmation` 流程 | ⚠️ 框架层"待用户确认"信号（钩子返回 `Reject(confirmation_required)`）已在 `base.py` 文档中描述但**当前 orchestrator 是否完整实现**需 Phase 1 验证；如未实现，需先补 orchestrator 的 confirm-replay 流程 |
| `audit_log` Hook | ⚠️ Phase 3 决策：直接写 `ScheduleSwapAuditLog`，避免引入新 Hook 类型 |

### 5.3 向后兼容

- 既有 `schedule_tool.py` 不动
- `INTENT_PROMPT` / `TOOL_CHAIN_PROMPT` 增量修改，旧意图词不变
- Registry 注册顺序：swap 工具在 schedule 工具之后，不影响既有意图分类
- 前端 `QuickAssistant.jsx` 仅在 `awaiting_confirmation` 信号存在时弹窗，否则行为不变

---

## 6. 验收标准

- [ ] 用户在 `QuickAssistant` 输入 "我想和李四换下周三的班"，能正确弹出确认卡，目标姓名 = 李四，日期 = 本周三
- [ ] 确认后 swap-requests 数据库多一条 `requester=当前用户, target_personnel=李四, original_schedule.id=本周三排班` 记录
- [ ] 二次确认取消后数据库无新增
- [ ] 目标姓名打错（如"李武"）时返回友好错误，不弹确认卡
- [ ] **接收方**李四在 QuickAssistant 输入"同意张三的换班"，能弹出确认卡显示"将对 张三 的换班申请执行 同意"，确认后状态变为 approved
- [ ] **接收方**李四在 QuickAssistant 输入"拒绝张三的换班"，确认后状态变为 rejected_by_target
- [ ] 接收方决策时若多个申请 pending，必须先通过 query 工具列出，强制二次确认指明申请号
- [ ] 速率限制：1 分钟内 11 次写请求，第 11 次返回 429
- [ ] pytest 覆盖 swap_request_tool ≥ 80%
- [ ] 前端 E2E（vitest）：模拟成功 / 取消 / 错误 / 接收方决策 4 条路径

---

## 7. 后续可扩展（本期不做）

- LLM 帮接收方 accept/reject（需用户显式开启"代签"开关，且双因素二次确认）
- 批量换班（"这周全部和我同事小王互换"）
- 智能推荐换班对象（基于排班密度、轮换公平性）
- 语音输入 + 多轮对话澄清

---

## 8. 决策日志

| 决策 | 选择 | 理由 |
|---|---|---|
| 接收方决策是否由 LLM 代理 | ✅ **允许**接收方在 QuickAssistant **主动**发起决策指令（说"同意李四的换班"） | 用户决定（2026-08-04）：接收方本人操作合规；LLM **不得**在用户未说话时自动决策 |
| 接收方决策合规闸门 | LLM 必须先 query 出具体 swap_id + 申请人 + 日期，列出"将对 XX 的换班执行 同意/拒绝"，等二次确认 | 防误判、防 race、防 LLM 静默代签 |
| 写工具速率限制 | 每用户每分钟 **10 次**（create + decide 共用配额） | 用户决策（2026-08-04）：内网场景，10/min 留足余量又不至于完全无防 |
| Phase 1 起步条件 | **必须先做步骤 1.0 框架验证闸门** | 用户决策（2026-08-04）：避免在 `require_confirmation` 框架未跑通前做大量业务开发导致返工 |
| 写工具风险等级 | `write` + `require_confirmation=True` | 不可逆操作（一旦发出就通知接收方），但非破坏性 |
| 是否复用 ViewSet 业务逻辑 | ✅ 直接 import 复用 `perform_create` / `accept` / `reject` / `cancel` 内部规则 | 避免逻辑双写 |
| 关键词 vs LLM 分类 | 关键词先粗筛 + LLM 二次确认 | 减少误触发，降低 LLM 调用 |
| 速率限制位置 | middleware 而非工具内 | 统一所有 write 工具的风控 |

---

## 9. 参考

- `omni_desk_backend/smart_assistant/tools/base.py` 第 47–74 行：风险等级与确认流程约定
- `omni_desk_backend/smart_assistant/agent/prompt_builder.py` 第 59–84 行：现有 INTENT_PROMPT 模式
- `omni_desk_backend/smart_assistant/agent/tool_chain_planner.py` 第 51–68 行：关键词表模式
- `omni_desk_backend/events/views/swap.py`：完整 CRUD 与状态机参考
- `omni_desk_backend/events/models.py` 第 247–433 行：`ScheduleSwapRequest` 模型字段
- `docs/technical/...` 中现有"智能助手"章节
- 全局规则：`feature-development.md`、`feature-branch-workflow.md`、`testing.md`

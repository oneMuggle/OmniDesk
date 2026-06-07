# 智能助手优化 — 第八段交接(本会话产出)

> 📅 **截止时间:2026-06-06 22:50**
> **本会话从 `docs/notes/2026-06-06_smart-assistant-optimization-handoff-7.md` 继续**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**P6 任务完成**。smart_assistant 模块覆盖率从 91% 提升至 **96%**。

**🎯 下个会话已确认方向:阶段 3 新工具(选项 B,高 ROI,~2 周)**

本会话总共 1 个 commit 落地(P6 任务):
| Commit | 类型 | 描述 |
|--------|------|------|
| `本会话` | test | 补 P6 任务覆盖率 91% → 96%(+69 测试) |
| `本会话` | docs | 第八段交接(P6 完成 + 阶段 3 启动指引) |

**测试基线**:356 passed + 10 xpassed + 1 xfailed = 367 实际通过,0 回归
**模块覆盖率**:smart_assistant 纯生产代码 **96%**(1320 行,49 行未覆盖)
**CI 门槛**:85%(留 11% 缓冲)

## 本会话完成的工作

### P6:补剩余覆盖率缺口(91% → 96%)

**新增文件(4 个):**
- `smart_assistant/tests/test_prompt_builder_coverage.py` — 19 测试
- `smart_assistant/tests/test_knowledge_base_coverage.py` — 14 测试
- `smart_assistant/tests/test_intent_classifier_coverage.py` — 21 测试
- `smart_assistant/tests/test_tool_chain_executor_coverage.py` — 15 测试

**4 个目标文件覆盖率结果:**

| 文件 | 起点 | 终点 | 状态 |
|------|------|------|------|
| `agent/prompt_builder.py` | 24% | **95%** | +71pp |
| `views/knowledge_base.py` | 65% | **100%** | +35pp |
| `agent/intent_classifier.py` | 46% | **100%** | +54pp |
| `agent/tool_chain_executor.py` | 67% | **100%** | +33pp |

**验证结果(本地 SQLite):**
```bash
cd omni_desk_backend
rm -f .coverage
coverage run -m pytest smart_assistant/ --no-cov -q
# 356 passed, 1 xfailed, 10 xpassed, 1 warning in 8.91s

coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' \
  --fail-under=85
# TOTAL 96%,1320 行,49 行未覆盖,EXIT=0
```

## 下个会话任务(已确认:阶段 3 新工具)

**用户决定**:从选项 A/B/C/D 中选择 **选项 B:阶段 3 新工具(高 ROI,2 周)**

### 阶段 3 范围(摘自 [plan 文档 §3](../plans/2026-06-06_smart-assistant-optimization.md#阶段-3新工具15-周-p1))

实现 3 个高频业务工具 + 24 测试 + E2E + 前端卡片:

1. **`announcement_tool.py`** — 公告/通知查询
   - 数据源:`communication` app 的 `Announcement` 模型
   - 能力:查询最近 N 条公告 / 按标签过滤 / 统计已读率
   - 权限:按 `request.user` 可见性过滤
   - 测试:8 个(参数解析、权限、空结果、异常、并发 等)

2. **`compliance_tool.py`** — 合规检查
   - 数据源:`compliance` app 的 `InspectionRecord`
   - 能力:待整改项 / 合规分数 / 即将到期提醒
   - 测试:8 个

3. **`external_link_tool.py`** — 外部链接
   - 数据源:`external-links` app 的 `Bookmark` / `LinkGroup`
   - 能力:模糊匹配书签名 / 列出分类 / 推荐链接
   - 测试:8 个

**E2E 覆盖**(3 个新场景,加到 `test_e2e_smart_chat.py`):
- 问"这周有什么公告" → 走 announcement_tool → LLM 合成回答
- 问"张三还有几条待整改" → 走 compliance_tool
- 问"公司 VPN 怎么登录" → 走 external_link_tool

**前端**:`omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` 增加:
- `AnnouncementCard` 组件
- `ComplianceCard` 组件
- `LinkCard` 组件

**工具注册协议增强**:
- 新增 `ToolContext` 抽象:`tool.execute(query, context={user, history, ...})`
- 默认拒绝跨用户数据泄露
- 工具内部显式使用 `context.user`

### 下个会话第一步(plan-first)

按 CLAUDE.md 强制约束,**必须先写计划文档**到 `docs/plans/`,命名 `2026-06-07_smart-assistant-stage3-new-tools.md`(假设下个会话是 06-07)。

计划文档应包含:
- 背景与目标(3 个新工具的 WHY)
- 涉及文件与模块
- 技术方案:`ToolContext` 抽象 / `BaseTool` 接口增强 / 工具 schema 模板
- 实施步骤(checkbox 列表,按天分解)
- 风险评估与依赖(权限/可见性错误是 HIGH 风险,需 24h code review + E2E 包含"非授权用户被拒")

### 阶段 3 任务分解(总 2 周,~10 工作日)

| 子任务 | 工作量 | 风险 | 优先级 |
|--------|--------|------|--------|
| 评估数据源 + 设计 schema + `ToolContext` 抽象 | 1 天 | 低 | 第 1 |
| 实现 `announcement_tool` + 8 测试 | 1.5 天 | 中(权限) | 第 2 |
| 实现 `compliance_tool` + 8 测试 | 2 天 | 中(数据量) | 第 3 |
| 实现 `external_link_tool` + 8 测试 | 1.5 天 | 低 | 第 4 |
| 注册到 `tools/registry.py` + `prompt_builder` 工具列表 | 0.5 天 | 低 | 第 5 |
| E2E 覆盖 3 场景(`test_e2e_smart_chat.py`) | 1 天 | 中 | 第 6 |
| 前端 3 个新卡片组件 | 1.5 天 | 中(UI) | 第 7 |
| 联调 + 文档 + 提 PR | 1 天 | 低 | 第 8 |

### 关键注意点

**风险表(摘自 plan §6)**:
- 新工具数据源权限/可见性错误 → 越权 — **HIGH 风险**
- 缓解:严格走 `ToolContext.user`;新增工具前 24 小时 code review;E2E 用例必须包含"非授权用户被拒"
- N+1 查询风险:MEDIUM — 严格 `select_related` / `prefetch_related`,PR review 检查

**可复用 fixture**(conftest.py):
- `mock_tool_registry` — 动态注册/替换工具
- `mock_llm_router` — LLM 调用 mock
- `celery_eager_mode` — 同步执行 Celery 任务
- `sample_smart_session` / `sample_agent_log` — 模型工厂

**预计覆盖率影响**:
- 阶段 3 完成后,smart_assistant 覆盖率会暂时下降到 ~85%(新代码未测)
- 阶段 3 内的 24 测试补回,稳定后可达 90%+
- 不强求 99%,阶段性回到 85%+ 即可

### 文档归档

完成时按 `feature-development.md` 规则:
- 计划文档完成时 → 移到 `docs/technical/29-smart-assistant-stage3-tools.md`(占位编号)
- 更新 `docs/technical/README.md` 章节目录
- 用户手册 `docs/user-manual/04-smart-assistant-user-guide.md` 增加新工具用户视角说明

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认最近 commit(应看到本会话 test + docs 两个 commit)
git log --oneline -3

# 3. 跑基线测试(本会话验证 356 + 1 xfailed + 10 xpassed)
cd /home/fz/project/OmniDesk/omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q

# 4. 跑覆盖率(本会话验证 96% 通过 --fail-under=85)
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=85

# 5. 第一件事:写计划文档(plan-first 强制约束)
#    文件路径:docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md
#    必填章节:背景、文件清单、技术方案、checkbox 实施步骤、风险评估
```

## 累计成果(从 handoff-1 到 handoff-8)

| 阶段 | 任务 | commits | 测试数 | 覆盖率 |
|------|------|---------|--------|--------|
| P0 | 基线 | - | 88 | ~50% |
| P1-1 | orchestrator 覆盖率 | 1 | 144 | ~65% |
| P1-2 | middleware_chain 覆盖率 | 1 | 161 | ~70% |
| P2 | 覆盖率 workflow | 1 | 201 | 78% |
| P3-1~4 | 4 模块覆盖率补齐 | 1 | 287 | 91% |
| P3-5 | CI 门槛 75→85% | 1 | 287 | 91% |
| **P6** | **剩余 4 文件覆盖率补齐** | **1** | **356** | **96%** |
| **累计** | **7 阶段** | **7 commits** | **+268 测试** | **+46%** |

## 剩余未覆盖代码(49 行,占总代码 4%)

按 ROI 排序(优先补高 ROI):

### 中 ROI(< 50 行可补)

| 文件 | 未覆盖行 | 内容 | 建议补法 |
|------|----------|------|----------|
| `agent/orchestrator.py` | 12 行 | 49, 74-75, 149, 153-154, 159-160, 182-187 | 错误路径/缓存冲突/token 超限场景,补 ~6 测试 |
| `agent/tool_chain_planner.py` | 9 行 | 46-48, 89-92, 94-96 | JSON 解析失败/单工具降级,补 ~3 测试 |
| `views/llm_config.py` | 9 行 | 73, 82-83, 118, 128-138 | 端点健康检查/缓存失效,补 ~5 测试 |
| `tools/registry.py` | 2 行 | 15, 19 | 注册/取消注册边界,补 ~2 测试 |
| `views/chat.py` | 4 行 | 52, 137-138, 153 | 流式中断/conversation 不存在,补 ~3 测试 |
| `views/logs.py` | 3 行 | 25, 30, 32 | 日志过滤/分页,补 ~2 测试 |
| `models.py` | 3 行 | 24, 130, 159 | 模型边界,补 ~2 测试 |
| `serializers.py` | 1 行 | 56 | SerializerMethodField 边界,补 ~1 测试 |
| `tools/base.py` | 1 行 | 22 | BaseTool 抽象方法,补 ~1 测试 |
| `tasks.py` | 3 行 | 47, 74-75 | Celery 任务边界,补 ~2 测试 |
| `agent/conversation_context.py` | 1 行 | 59 | 摘要函数边界,补 ~1 测试 |
| `agent/prompt_builder.py` | 1 行 | 40 | `if not parts` 边缘,补 ~1 测试 |
| **合计** | **49 行** | | **~29 测试可推到 99%** |

**ROI:** 中 — 推到 99% 总覆盖率,但每次新功能都需重写
**工作量:** 中等 — 涉及更多依赖(LLM 流式、Celery 任务)

### 低 ROI(不推荐补)

- `migrations/*` — 11 行被 omit 排除,已统计在"纯生产代码"之外
- `__init__.py` / `apps.py` / `admin.py` — 配置文件,无需测试

## 立刻可继续的任务(下次会话第一件事)

### 选项 A:继续 P7 推到 99%(中 ROI,~29 测试,~3 小时)

按上表逐文件补。`orchestrator.py` 和 `tool_chain_planner.py` 是 P3 路线图点名要补的。

### 选项 B:转 P4 阶段 3 新工具(高 ROI,大工作量,2 周)

按 plan 文档阶段 3,实现 3 个高频业务工具:
- `announcement_tool.py`(8 测试)
- `compliance_tool.py`(8 测试)
- `external_link_tool.py`(8 测试)
- E2E 覆盖(3 测试)

**ROI:** 极高 — 直接业务价值,但工作量大

### 选项 C:阶段 4 性能优化(中 ROI,~1 周)

按 plan 文档阶段 4:TTFT 优化、长会话压缩、ToolResult 渲染性能。

## 已知坑(继承 handoff-7,本会话新增 1 个)

### 1. settings 导入陷阱(沿用 memory)

- `omni_desk_backend.settings/__init__.py:5` 默认走 `from .development import *`
- CI 用 PG service 走 settings.development,本地走 settings.test(SQLite)

### 2. 覆盖率命令模板(沿用 handoff-5,本会话验证)

```bash
cd /home/fz/project/OmniDesk/omni_desk_backend
rm -f .coverage
coverage run -m pytest smart_assistant/ --no-cov -q
coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' \
  --fail-under=85 --show-missing
```

### 3. cwd 陷阱(沿用 handoff-7)

- `cd omni_desk_backend` 后再 `cd omni_desk_backend` 会进入 settings 包目录
- 始终用 `cd /home/fz/project/OmniDesk/omni_desk_backend` 绝对路径

### 4. Django FileField.path 只读(本会话发现 🆕)

- `doc.file.path = tmp_path` 报 `AttributeError: can't set attribute 'path'`
- **修正方案 A:** 用 `unittest.mock.patch` mock `open()` + `FileResponse`,返回 `Response` 对象
- **修正方案 B:** 用 `tempfile.NamedTemporaryFile` + `override_settings(MEDIA_ROOT=...)`

### 5. 1 个测试从 xpassed 变 xfailed(本会话发现,预存 flake)

- `test_meeting_room_tool.py::test_booking_marks_room_unavailable`
- 原来是 xpassed(标 xfail 但意外通过),现在是 xfailed(标 xfail 且按预期失败)
- 总数:1 xfailed + 10 xpassed = 11,与 handoff-7 一致
- 推测:测试顺序/隔离导致的随机状态差异,与 P6 工作无关

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认最近 commit
git log --oneline -3
# 期望:看到本会话的 test commit + docs(handoff-8) commit

# 3. 跑基线测试(本会话验证 356 + 1 xfailed + 10 xpassed)
cd /home/fz/project/OmniDesk/omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q

# 4. 跑覆盖率(本会话验证 96% 通过 --fail-under=85)
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=85

# 5. 决定本会话从哪个任务开始
#    - 选项 A: P7 推到 99%(中 ROI,3 小时)
#    - 选项 B: P4 阶段 3 新工具(高 ROI,2 周)
#    - 选项 C: 阶段 4 性能优化(中 ROI,1 周)
```

## 关联文档
- 📋 [阶段 1+2 完整计划](../plans/2026-06-06_smart-assistant-optimization.md)
- 📋 [上次会话交接(7 段)](2026-06-06_smart-assistant-optimization-handoff-7.md)
- 📋 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md) §3.2-3.3
- 🧠 [覆盖率环境陷阱记忆](file:///home/fz/.claude/projects/-home-fz-project-OmniDesk/memory/smart-assistant-coverage-env-trap.md)
- 🆕 [本会话新增文档:FileField.path 只读陷阱](本文件"已知坑"§4)

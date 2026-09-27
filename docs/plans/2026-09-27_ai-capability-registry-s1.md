# AI 能力注册中心（S1）实施计划

> 日期：2026-09-27
> 分支：`feat/ai-capability-registry-s1`（基于 `origin/main` `c38daa0`，即 #497 合并后）
> 依据：`docs/mcp-ai-orchestration-plan.md` 第 5.1 节
> 状态：已实施，待推送与 PR 评审

## 背景与目标

现在 24 个 AI 工具都在 `smart_assistant/apps.py` 里手工 import、逐个注册。这带来三个问题：

1. 业务模块不知道自己有哪些 AI 能力，模块目录里的 AI 一栏只能手工维护；
2. 工具的权限、数据范围、是否需要确认，散落在各工具类的属性和注释里，没有统一声明，也没有启动时的检查；
3. 后续 S3 要加写操作（会议室预约等），没有地方声明"需要确认""能否回滚""是否默认关闭"。

本批做一个**能力注册中心**：各 app 用 `ai_tools.py` 声明自己的工具集，`smart_assistant` 在启动时自动发现并做自检；再补 4 个只读工具，并由代码自动生成能力目录。

## 范围

| # | 事项 |
| --- | --- |
| C1 | 新增 `smart_assistant/capabilities` 包：`ToolSpec`、`toolset` 装饰器、`CapabilityRegistry`、自动发现、启动自检 |
| C2 | 24 个现有工具原样迁移到 16 个 app 的 `ai_tools.py`；`apps.py` 改为自动发现。工具类文件位置不变，行为不变 |
| C3 | `required_permission` 生效：注册中心提供按用户的权限判断，原生工具调用、链式执行、旧意图路由三条路径都经过它 |
| C4 | 新增 4 个只读工具：`notification_query`（通知）、`joint_student_query`（联培生）、`communication_thread_query`（交流帖子与评论）、`document_library_query`（文档库） |
| C5 | 自动生成能力目录 `docs/technical/46-ai-capability-catalog.md`，管理命令 `ai_capabilities` 支持 `--write`、`--check`；测试保证目录与代码一致；`45-module-catalog.md` 的 AI 列改为引用该目录 |
| C6 | 文档：技术手册、CLAUDE.md 中"工具注册在 apps.py"的描述同步更新 |

**不在本批：** AI 抽屉（S2）、五项写操作（S3）、数字员工（S4）。`confirm`、`rollback`、`feature_flag` 只定义字段与校验规则，没有工具使用。

## 设计

### ToolSpec 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `tool` | 是 | `BaseTool` 子类，或它的点分路径（延迟导入） |
| `title` | 是 | 中文短名，用于能力目录 |
| `required_permission` | 是 | `LOGIN_ONLY`（登录即可，数据由 `data_scope` 限制），或 Django 权限码 `app_label.codename` |
| `data_scope` | 是 | 数据范围策略：`scope`（SELF / DEPARTMENT / GLOBAL）、`owner`（只看本人数据）、`module`（复用模块自身接口的可见性规则）、`delegated`（委托给其他工具的 scope）、`attachment`（只读本次请求附件）、`knowledge`（知识库检索，不含用户私有数据）、`recipient`（写给他人时按发起人 scope 限定收件人，如 `agent_notify`） |
| `confirm` | 否 | `none` / `user`（单人确认）。写操作与删除必须为 `user`，且必须与工具类的 `require_confirmation` 一致 |
| `idempotent` | 否 | 默认只读为 True、写为 False |
| `open_world` | 否 | 是否访问外部系统（如 RAGFlow） |
| `rollback` | 否 | 预留，S3 使用（如 `agent_write_log`） |
| `feature_flag` | 否 | 预留：填写后，只有 `settings.<flag>` 为真时才注册该工具 |
| `version` | 否 | 默认 `1` |

`read_only` / `destructive` 不再重复声明，由工具类的 `risk_level` 推导，并输出 MCP ToolAnnotations 四个提示（`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint`）。

### 自动发现

- 各 app 的 `ai_tools.py` 用 `@toolset(name, title=...)` 装饰一个返回 `ToolSpec` 列表的函数；函数体内再 import 工具类，避免导入期循环依赖。
- `SmartAssistantConfig.ready()` 按 `INSTALLED_APPS` 顺序导入各 app 的 `ai_tools` 模块。模块本身报错时直接抛出，不静默吞掉。

### 启动自检（失败即抛 `ImproperlyConfigured`，启动失败）

1. `intent` 不重复；toolset 名不重复；
2. `required_permission` 为 `LOGIN_ONLY` 或 `app_label.codename` 格式；
3. `data_scope`、`confirm` 取值合法；
4. `risk_level` 为 write / destructive 时 `confirm="user"`，并与 `require_confirmation` 一致；只读工具不得声明确认或回滚；
5. OpenAI schema 结构合法、`strict=True`，每层 object 都是 `additionalProperties=false`，`name` 等于 `intent`；
6. `data_scope="scope"` 的工具必须自己实现 `build_base_queryset()` 与 `_scope_self()`。

权限码是否真实存在于数据库，放在管理命令 `ai_capabilities --check` 和测试里检查（启动时数据库可能还没迁移）。

### 权限判定

`CapabilityRegistry.is_permitted(intent, user)`：

- 未登记 spec 的工具（测试里的桩）→ 放行，保持兼容；
- `LOGIN_ONLY` → 放行（登录校验仍由 `required_auth` 负责）；
- Django 权限码 → `user.has_perm()`，superuser 天然通过。

接入点：`ToolRegistry.get_tool_for_user()`、`ToolRegistry.get_openai_tools()`；旧意图路由（orchestrator 单工具路径、流式单工具路径、函数式链执行）在原有 `get_tool()` 之后追加 `ToolRegistry.is_permitted()` 判定。旧路径不改为 `get_tool_for_user()`，是为了不改变它原有的登录语义，也不影响 60 多处 mock `get_tool` 的测试。现有 24 个工具都登记为 `LOGIN_ONLY`，所以行为不变。

### 新增只读工具

| intent | app | 数据范围 | 说明 |
| --- | --- | --- | --- |
| `notification_query` | `notifications` | `owner` | 只查本人通知；支持未读筛选、类型筛选、未读数。任何 scope 都不能看他人通知 |
| `joint_student_query` | `joint_students` | `module` | 与 `/api/joint-students/` 相同：管理员组 / superuser 看全部，导师看名下，本人看自己。可见性逻辑抽到 `joint_students/services/access.py`，视图与工具共用 |
| `communication_thread_query` | `communication` | `module` | 与交流接口一致（登录用户可读所有未归档帖子）；返回帖子与最近评论，补足 `announcement_query` 只列标题的不足 |
| `document_library_query` | `paperless_proxy` | `module` | 与 `/api/paperless/documents/` 一致：staff 看全部，其他人只看自己上传的文档；只查本地 `DocumentBinding`，不调用 Paperless 服务账号 |

意图分类提示词和链式规划关键词同步加入这 4 个 intent。

## 任务清单

- [x] C1 capabilities 包 + 单元测试（校验规则逐条覆盖）
- [x] C2 16 个 `ai_tools.py`；`apps.py` 改为自动发现；工具数与 intent 集合断言
- [x] C3 权限判定接入三条路径 + 测试
- [x] C4 4 个新工具 + 测试（每个都有越权用例）
- [x] C5 能力目录生成命令 + 生成文档 + 一致性测试；45 号文档改引用
- [x] C6 文档同步
- [x] 后端全量测试、ruff、前端不受影响确认
- [ ] 推送、开 PR、CI 全绿

## 验证记录（2026-09-27，沙箱）

- 后端全量：`pytest --ds=omni_desk_backend.settings.test` → 3297 passed、2 skipped，覆盖率 93.34%（门槛 80%）。
- 新增测试：`smart_assistant/tests/test_capabilities.py` 45 个用例，覆盖自动发现、自检规则逐条、feature_flag、权限矩阵、三条执行路径中的函数式工具链、MCP 注解、能力目录一致性与管理命令、新 intent 关键词不误触发多工具；4 个新工具各有测试文件，并与对应 HTTP 接口逐角色比对可见范围。
- `python manage.py ai_capabilities --check`：能力目录与代码一致（28 个工具），所有权限码均存在。
- `ruff check omni_desk_backend/`、`ruff format --check omni_desk_backend/`：全部通过。
- 前端：本批未改前端代码。新工具的结果在对话中以文字回答呈现，专用结果卡片留到 S2（AI 抽屉）。

## 风险

| 风险 | 应对 |
| --- | --- |
| 注册顺序从手写顺序变成 `INSTALLED_APPS` 顺序，LLM 看到的同风险等级工具顺序会变 | 只影响排列，不影响可用集合；全量测试验证 |
| 自检过严导致启动失败 | 规则都针对声明错误，现有 24 个工具已逐条满足；测试覆盖 |
| 新工具泄露数据 | 每个工具复用模块接口的同一套可见性逻辑，并写越权测试 |
| 能力目录与代码不一致 | 一致性测试在 CI 中失败，提示运行 `python manage.py ai_capabilities --write` |

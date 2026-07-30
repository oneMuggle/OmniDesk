# OmniDesk 项目优化方案(第一轮)

> 日期:2026-07-30 | 状态:实施中
> 调研方式:5 个并行 subagent(后端性能 / 前端质量 / 安全配置 / 死代码与依赖 / 测试与CI)

## 1. 背景与目标

对 OmniDesk 全栈代码库进行系统性健康度调研(后端 29 个 app、325 个非测试 Python 文件;前端 235 个 JS/JSX 文件、约 27.5K 行),发现以下四类可快速修复的问题。本轮目标:**在不进行大规模重构的前提下,消除 1 个 CRITICAL 安全漏洞、修复 6 处 N+1 查询与 1 个前端组件 bug、补齐 6 处索引、清理约 1.5K 行死代码与 11 个死依赖**。

整体健康度基线(调研结论):后端测试覆盖率 90.5%(高于 80% 门禁)、production settings 加固良好、无硬编码秘密、Axios 单例约定执行到位。问题集中在局部。

## 2. 优化项清单与技术方案

### A. 安全修复(最高优先级)

| # | 级别 | 位置 | 问题 | 修复方案 |
|---|---|---|---|---|
| A1 | CRITICAL | `documents/file_processing.py:83-86` | 上传文件名未净化即拼接路径,`os.path.join(temp_dir, file_obj.name)` 可被绝对路径/`../../` 穿越,经 `DocumentTemplateViewSet.upload_template`(仅需 IsAuthenticated,游客登录 AllowAny)可达任意文件写入 | 文件名经 `os.path.basename` + `django.utils.text.get_valid_filename` 净化;拒绝净化后为空的文件名 |
| A2 | LOW | `documents/book_import.py:88` | 同类未净化拼接(仅管理员可触发) | 同 A1 净化方式 |
| A3 | HIGH | `external_integration/views.py` + `plugin_service.py` | 插件系统越权:任意已认证用户可创建插件、上传 zip、自我批准(review 动作无权限校验);`plugin_sandbox.py` 名为沙箱实为裸 subprocess | `PluginViewSet` 的 create/upload_version/review/destroy 收紧为 `IsAdminUser`;`execute_plugin` 增加 `plugin.status == "approved"` 校验 |
| A4 | HIGH | `external_integration/views.py:55-80` | SSRF:任意用户可创建指向内网的 `endpoint_url`,call 动作由服务端发起请求且响应原样回传 | `IntegrationServiceViewSet` 写操作限管理员;`endpoint_url` 增加主机校验(禁回环/元地址段) |
| A5 | LOW | `health.py:31` | DB 故障时 `str(e)` 进响应,泄露连接细节 | 详情只写日志,响应仅返回 `"database": "error"` |

**本轮不做**(记录备查):`users/views.py` django_admin_login 的 JWT GET 传递(MEDIUM,需前后端联动改造,列入第二轮);插件真沙箱隔离(架构级,需独立方案)。

### B. 后端性能

**B1. N+1 查询修复(6 处)**

| # | 位置 | 修复 |
|---|---|---|
| B1.1 | `communication/views.py:23` | PostViewSet queryset 加 `.prefetch_related("comments__author")` |
| B1.2 | `communication/views.py:38` | CommentViewSet.get_queryset 补 `.select_related("author")`(重写时丢失了类级 queryset 的预取) |
| B1.3 | `events/views/sequences.py:21` | PersonnelSequenceViewSet 加 `.prefetch_related("holiday_personnel")` |
| B1.4 | `paperless_proxy/serializers.py:47` | get_outbox_status 逐行 `outbox.order_by().first()` → 视图层 `Prefetch` 窗口化或 `Subquery` annotate |
| B1.5 | `permissions/serializers.py:20` + `views.py:29` | PageRoute 递归树每节点 2 次查询 → 视图层一次性取全表、内存构树后序列化 |
| B1.6 | `users/views.py:241` | UserPersonnelViewSet queryset 加 `.select_related("personnel")` |

**B2. 缺失索引(6 处)+ 生成 migration**

| 模型 | 索引 | 依据 |
|---|---|---|
| `smart_assistant.AgentTask` | `Index(fields=["user", "-created_at"])` | `filter(user=...).order_by("-created_at")` 高频(同文件 ToolChainPlan 已有先例) |
| `communication.Post` | `Index(fields=["is_archived", "-created_at"])` | 主列表恒定过滤+排序 |
| `events.Announcement` | `created_at db_index=True` | `ordering=["-created_at"]` + dashboard 高频 |
| `sensor_management.Sensor` | `status db_index=True` | 按状态过滤/计数 |
| `projects.Project` | `status db_index=True` | dashboard `filter(status=...).count()` |
| `notifications.Notification` | type 纳入复合索引 | 列表 `filter(type=...)` |

### C. 前端修复

| # | 位置 | 问题 → 修复 |
|---|---|---|
| C1 | `features/personnel/pages/PersonnelManagementPage.jsx:177` | **[Bug]** render 体内定义内联 `PositionManagementTab` → 父组件每次渲染子树卸载重建、状态丢失,且遮蔽了 `components/PositionManagementTab.jsx` 同名独立组件 → 删除内联定义,改 import 现有组件(立减 ~120 行) |
| C2 | 死代码 | 删除零引用组件:`BaseSidebar.jsx`(282 行)、`ui/SkeletonTable.jsx`、`Library/LibraryPage.jsx`;删除 8 个孤儿页面及同族 css/test(DifyAppManagementPage、NewsManagementPage、SensorMovementHistoryPage、StorageLocationManagementPage、BookImportPage、BookManageExportPage、CompliancePage、NotificationsPage) |
| C3 | `FamilyMemberTable.jsx` / `ProfessionalQualificationTable.jsx` | 99% 重复 copy-paste → 提取泛型 `CrudSubTable({ fetchApi, createApi, updateApi, deleteApi, columns, formFields })` |
| C4 | `features/system/VersionInfo.jsx`、`shared/pages/DashboardPage.jsx` | 手动 useEffect+setState 取数 → 迁移 TanStack `useQuery`(项目约定) |

### D. 依赖与仓库卫生

| # | 内容 |
|---|---|
| D1 | 删除 `events/legacy_django_testcase.py`(468 行,pytest 永不收集、零 import、ruff 专门 exclude);同步清 `pyproject.toml` exclude 条目 |
| D2 | 移除后端 `django-ckeditor`(全项目零使用、CKEditor 4 已 EOL 有已知 XSS);pip-compile 重新生成锁文件 |
| D3 | 移除前端 10 个零引用依赖:react-dnd、react-dnd-html5-backend、file-saver、docxtemplater、mammoth、openai、jwt-decode、react-tooltip、web-vitals、dayjs-plugin-utc;同步清理 vite.config.js manualChunks 与 jest.config.js 同名条目;`npm install` 同步 lock。(tippy.js 为 @tiptap 间接依赖,待确认,**本轮不动**) |
| D4 | `.gitignore` 补 `/deployment/docker/*.zip`(现有 459MB `3冯志.zip` 未忽略,防误提交;文件本身不删,提示用户自行处置) |
| D5 | CI 修复:`deploy-test.yml` 的 `workflow_run` 引用了不存在的 workflow 名(触发链已断)→ 改为实际名 `"Build and Push Docker Images"`;清除 CLAUDE.md / AGENTS.md / docs/technical/04-testing-strategy.md 中已删除的 `ci-test.yml` 残留引用(7 处);修正 CLAUDE.md 应用清单(`sensors` → `sensor_management`) |
| D6 | 清理 8 个已并入 main 的残留 git worktree |

## 3. 涉及的文件与模块

- 后端:`documents/`、`external_integration/`、`health.py`、`communication/`、`events/`、`paperless_proxy/`、`permissions/`、`users/`、`smart_assistant/models.py`、`sensor_management/models.py`、`projects/models.py`、`notifications/models.py`、`requirements*.in/txt`、`pyproject.toml`
- 前端:`src/features/personnel/`、`src/shared/components/`、`src/shared/pages/`、`src/features/{dify-apps,news,sensor,system}/`、`package.json`、`vite.config.js`、`jest.config.js`
- 配置/文档:`.github/workflows/deploy-test.yml`、`.gitignore`、`CLAUDE.md`、`AGENTS.md`、`docs/technical/04-testing-strategy.md`

## 4. 实施步骤(subagent 并行,按文件域隔离避免冲突)

### 阶段一:调研 ✅
- [x] 5 个并行调研 agent(后端性能/前端质量/安全/死代码/测试CI)

### 阶段二:并行实施(5 个 agent)
- [x] B1 后端安全组:A1–A5 全部完成,新增 30+ 安全回归测试(自验证 109 passed)
- [x] B2 后端性能组:6 处 N+1 全修(含路由树内存建树、窗口化 Prefetch、context 批量注入)+ 6 处索引 migration(自验证 1519 ran / 0 failed)
- [x] F1 前端代码组:C1–C4 完成(中途 API 超时一次,经 transcript 恢复续做);删除 16 个死文件;eslint 0 错 0 警
- [x] F2 前端依赖组:移除 10 个死依赖(56 包),lock 零残留,npm ls 正常
- [x] C1 卫生与CI组:legacy 文件删除、ckeditor 移除(锁文件仅 4 行 pin 删除)、gitignore 补规则、deploy-test 触发链修复、7 处过时文档引用清理、6 个 worktree 清理

### 阶段三:统一验证(2026-07-31)
- [x] 后端:`pytest`(OmniDesk conda 环境,settings.test)**2009 passed, 3 xfailed, 10 xpassed, 0 failed**;覆盖率 **91.54%**(≥80% 门禁,较基线 90.5% 提升)
- [x] 后端:`ruff check` 全过 + `ruff format --check` 全过(修复 communication/views.py 1 处格式)
- [x] 前端:`npm run lint` 0 输出;`jest` **94 suites / 499 tests passed**(4 skipped 为既有)
- [x] 前端:`npm run build` 成功(23.6s;chunk 体积警告为既有 antd 大包,非本轮引入)

### 阶段四:收尾
- [x] 在 feature 分支 `chore/project-optimization-round1` 上分组提交(不推送,待用户确认后走 PR)
- [ ] 用户确认合并后,按文档规范将本文档功能点并入 `docs/technical/` 对应章节并删除本计划文件

## 5. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| A3/A4 权限收紧可能影响现有普通用户的集成功能使用 | 调研确认插件/集成为管理类功能;read 类动作保持 IsAuthenticated |
| B1.4/B1.5 改写查询逻辑可能引入行为差异 | 改写后运行对应 app 既有测试 + `django_assert_num_queries` 抽查 |
| D2 pip-compile 可能因环境差异产生锁文件大面积漂移 | 在 OmniDesk 环境(Python 3.10 + pip-tools)执行;diff 审查,若漂移超出 ckeditor 移除范围则回滚锁文件仅保留 .in 变更 |
| D3 删依赖后 build 断裂 | `npm run build` 冒烟兜底;tippy.js/slick-carousel 等不确定项本轮不动 |
| 索引 migration 在生产需并发安全 | migration 仅 ADD INDEX,非破坏性;按项目升级规范先 backup 再 migrate(check_migrations 预检) |

**不在本轮范围**(高风险/大规模,记录备查):executor.py(892 行)拆分、ScheduleManagementPage(909 行)拆分、ScheduleManagementPage while 循环全量拉取(需新后端端点)、前端覆盖率阈值提升(当前 24%)、插件真沙箱、mypy 硬门禁化、E2E 接入 CI。

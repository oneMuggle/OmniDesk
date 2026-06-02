# 项目冗余清理计划

## 背景与目标

OmniDesk 项目在多次迭代中积累了大量冗余文件、目录和配置。这些包括：
- 功能重叠的 Django apps（sensors vs sensor_management）
- 错误操作产生的空壳目录
- 未引用的孤立目录
- 未纳入 .gitignore 的构建产物
- 分散重复的文档目录
- 过时的分析报告和工具配置

**目标**：清理冗余内容，简化项目结构，减少维护负担。

## 涉及的文件与模块

### 后端（omni_desk_backend/）
- `sensors/` - 废弃的传感器 app，功能已被 sensor_management 替代
- `omni_desk_backend/omni_desk_backend/*/` - 9 个空壳镜像目录
- `omni_desk_backend/omni_desk_backend/db.sqlite3` - 嵌套数据库副本
- `htmlcov/`, `coverage.xml`, `.coverage` - 测试覆盖率报告
- `docs/` - 空的后端文档目录

### 前端（omni_desk_frontend/）
- `smart_assistant/` - 孤立目录，无任何代码引用
- `build/` - CRA 构建产物
- `coverage/` - 测试覆盖率报告（518 个文件）
- `.ruff_cache/`, `.pytest_cache/` - Python 工具链缓存（不应出现在前端）
- `docs/` - 前端文档目录
- `src/shared/api/trials.js` - 与 trialApi.js 功能重叠
- `src/features/schedule/api/schedule.js` - 与 scheduleApi.js 功能重叠
- `.env`, `.env.example` - 与 .env.development/.env.production 重叠

### 根目录
- `.playwright-mcp/` - Playwright MCP 工具缓存
- `.roo/`, `.trae/`, `.sisyphus/`, `.night-work/`, `.opencode/`, `.cospec/` - 多 IDE 配置
- `OPTIMIZATION_REPORT.md`, `OPTIMIZATION_SUGGESTIONS.md`, `TEST_ANALYSIS.md`, `DIRECTORY_OPTIMIZATION.md` - 过时报告
- `shift-schedule-snapshot.yml` - 测试中间文件
- `tech_docs/` - 与 docs/ 重叠的旧文档
- `utils/` - 待确认是否仍使用
- `desktop_notifier/` - 独立桌面通知项目，待确认

### 配置文件
- `.gitignore` - 需要添加更多排除规则
- `omni_desk_backend/omni_desk_backend/settings/base.py` - INSTALLED_APPS 清理入口
- `omni_desk_backend/omni_desk_backend/urls.py` - URL 路由清理入口

## 技术方案

### Phase 1: 安全删除（无代码变更风险）

直接删除明确冗余的空目录和孤立文件，不影响任何运行代码。

### Phase 2: 代码清理（需要验证）

从 Django 配置中移除废弃 app，删除对应目录，统一前端重复 API 模块。

### Phase 3: 配置更新

更新 .gitignore，确保构建产物和缓存不会被提交。

### Phase 4: 整理归档

合并文档目录，清理过时报告，精简环境配置。

## 实施步骤

### Phase 1: 安全删除

- [x] 步骤 1：删除 9 个后端影子空壳目录
  - `omni_desk_backend/omni_desk_backend/communication/`
  - `omni_desk_backend/omni_desk_backend/dify_apps/`
  - `omni_desk_backend/omni_desk_backend/documents/tests/`
  - `omni_desk_backend/omni_desk_backend/events/tests/`
  - `omni_desk_backend/omni_desk_backend/meeting_rooms/`
  - `omni_desk_backend/omni_desk_backend/news/`
  - `omni_desk_backend/omni_desk_backend/office_assistant/`
  - `omni_desk_backend/omni_desk_backend/ragflow_service/`
  - `omni_desk_backend/omni_desk_backend/sensors/`

- [x] 步骤 2：删除嵌套数据库副本
  - `omni_desk_backend/omni_desk_backend/db.sqlite3`

- [x] 步骤 3：删除前端孤立目录
  - `omni_desk_frontend/smart_assistant/`

- [x] 步骤 4：删除后端空 docs 目录
  - `omni_desk_backend/docs/`

- [x] 步骤 5：删除前端文档目录（合并到根目录 docs/）
  - `omni_desk_frontend/docs/`

### Phase 2: 代码清理

- [x] 步骤 6：移除废弃的 sensors app
  - 从 `base.py` 的 INSTALLED_APPS 中移除 `sensors`
  - 从 `urls.py` 中移除 sensors 相关路由
  - 删除 `omni_desk_backend/sensors/` 整个目录

- [-] 步骤 7：检查并清理重复 API 模块（已分析，需后续重构，暂跳过）
  - `trials.js` 和 `trialApi.js` 不是纯重复，各有独有功能
  - `schedule.js` 是有用的 facade 模式

- [x] 步骤 8：检查 sensors 相关前端代码
  - 前端 `features/sensor/` 仅依赖 `sensor_management`，无对废弃 `sensors` app 的引用

### Phase 3: 配置更新

- [x] 步骤 9：更新 .gitignore
  - 添加构建产物排除（build/, coverage/, htmlcov/）
  - 添加缓存目录排除（.playwright-mcp/, .ruff_cache/, .mypy_cache/, .pytest_cache/）
  - 添加数据库文件排除（**/db.sqlite3）
  - 添加 IDE 配置排除（.sisyphus/, .night-work/, .opencode/, .cospec/）

- [x] 步骤 10：从仓库移除已跟踪的构建产物
  - `git rm --cached` 移除 `.coverage` 和 `coverage.xml`

### Phase 4: 整理归档

- [x] 步骤 11：处理过时报告文件
  - 已删除 OPTIMIZATION_REPORT.md, TEST_ANALYSIS.md, DIRECTORY_OPTIMIZATION.md, OPTIMIZATION_SUGGESTIONS.md, shift-schedule-snapshot.yml

- [-] 步骤 12：精简 .env 文件（暂保留，需确认前端构建配置后再处理）

- [x] 步骤 13：处理 tech_docs/ 目录
  - 已移动 10 个模块设计文档到 `docs/technical/`，已删除 tech_docs/ 目录

- [x] 步骤 14：确认 utils/ 和 desktop_notifier/ 是否仍使用
  - 两者均有 CI workflow 引用，保持现状

## 风险评估与依赖

### 风险

| 风险 | 级别 | 应对 |
|------|------|------|
| sensors app 仍被某些代码引用 | 中 | 删除前用 grep 全局搜索引用 |
| 重复 API 模块有外部消费者 | 低 | 删除前检查 import 引用 |
| .gitignore 更新影响其他开发者 | 低 | 使用 git rm --cached 不影响本地文件 |
| tech_docs/ 中有未被覆盖的文档 | 低 | 先检查内容再删除 |

### 依赖

- 无外部依赖
- 所有操作均可独立执行
- 每个 Phase 完成后项目应保持可运行状态

### 回滚方案

- 所有删除操作通过 git commit 记录，可通过 git revert 回滚
- 数据库副本删除前建议备份
- 建议在独立分支执行，确认无问题后合并

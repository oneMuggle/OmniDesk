# 2026-06-02_project-optimization.md

# OmniDesk 项目优化计划

## 背景与目标

OmniDesk 是一个包含 21+ Django 应用和大量 React 组件的全栈业务管理平台。经过代码质量分析，发现以下需要优化的关键领域：

1. **测试覆盖率偏低**（后端 40.1%，远低于 80% 标准）
2. **代码质量问题**（console.log 残留、宽泛异常捕获、N+1 查询风险）
3. **依赖冗余**（moment + dayjs 并存、未使用的依赖）
4. **大文件**（ScheduleManagementPage.jsx 909 行，多个文件接近上限）
5. **CI/CD 不可靠**（lint 和安全检查被设为 continue-on-error）
6. **前端 API 调用不一致**（多处绕过 axiosConfig 直接使用 axios）

## 已完成阶段

### Phase 1: 快速清理 ✅

| 项目 | 描述 | 状态 |
|------|------|------|
| 清理 console.log | 用 `logger.js` 工具替换所有 `console.log` | ✅ 已完成 (7个文件) |
| 移除 deprecated `default_app_config` | Django 4.2 已自动发现 | ✅ 已完成 (2个文件) |
| 清理死代码脚本 | 删除无用脚本 | ✅ 已完成 |

### Phase 3: API 调用统一化 ✅

| 项目 | 描述 | 状态 |
|------|------|------|
| 统一使用 axiosConfig | 替换直接 `import axios` 为使用带拦截器的实例 | ✅ 已完成 (9个文件) |

### Phase 4: N+1 查询修复 ✅

| 项目 | 描述 | 状态 |
|------|------|------|
| 添加 select_related | TimeSlotViewSet 添加 `select_related('trial')` | ✅ 已完成 |

## 待执行阶段

### Phase 2: 依赖优化 — moment → dayjs 迁移 ✅

| 项目 | 描述 | 状态 |
|------|------|------|
| 统一日期库 | 移除 `moment`，全部迁移到 `dayjs` | ✅ 已完成 (14个源文件 + 2个测试文件) |
| 移除 moment 依赖 | 从 package.json 中删除 | ✅ 已完成 |
| 添加 dayjs 插件 | `weekOfYear`, `isBetween` 全局注册 | ✅ 已完成 |

**涉及文件：**
- `src/index.jsx` — 添加 `weekOfYear`, `isBetween` 插件
- `package.json` — 移除 `moment` 依赖
- `features/schedule/hooks/useCalendar.js` — 默认参数 `moment()` → `dayjs()`
- `features/schedule/utils/computeWeeklyLeaders.js` — `.week()`, `.isBetween()`, `.clone()`
- `shared/components/Schedule/MonthlyLeaderSidebar.jsx` — `.week()`
- `features/personnel/pages/PersonnelEditPage.jsx` — 日期包装
- `features/sensor/pages/SensorMovementHistoryPage.jsx` — `.format()`, `.unix()`
- `features/sensor/pages/SensorCalibrationHistoryPage.jsx` — `.format()`
- `features/news/pages/NewsManagementPage.jsx` — DatePicker 绑定
- `features/schedule/components/ShiftScheduleContainer.jsx` — `.format()`
- `features/schedule/pages/HolidayManagementPage.jsx` — DatePicker 绑定
- `features/schedule/pages/ScheduleManagementPage.jsx` — 多处日期操作
- `features/memo/pages/MemoPage.jsx` — `.isBetween()`, `.clone()`
- `features/schedule/hooks/useCalendar.test.js` — 移除 moment mock
- `features/personnel/pages/PersonnelEditPage.test.js` — 测试日期
- `features/memo/pages/MemoPage.test.js` — 测试日期

### Phase 5: 大文件拆分（待执行）
### Phase 6: CI/CD 可靠性提升（待执行）

### Phase 7: 安全加固 ✅

| 项目 | 描述 | 状态 |
|------|------|------|
| 生产环境安全头 | 添加 `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT` 等 | ✅ 已完成 |
| 细化异常处理 | 将宽泛的 `except Exception` 替换为具体异常 | ✅ 已完成 (users/views.py) |

**涉及文件：**
- `settings/production.py` — 添加 SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS (1年), SECURE_HSTS_INCLUDE_SUBDOMAINS, SECURE_HSTS_PRELOAD, SECURE_CONTENT_TYPE_NOSNIFF, X_FRAME_OPTIONS
- `users/views.py` — `except Exception` → `except IntegrityError`

## 剩余待执行阶段

### Phase 5: 大文件拆分（高复杂度）

| 项目 | 描述 | 涉及文件 |
|------|------|----------|
| 拆分 ScheduleManagementPage | 将日历、拖拽、PDF导出拆为独立组件 | `features/schedule/pages/ScheduleManagementPage.jsx` (909行) |
| 拆分 AiAppManagementPage | 将 LLM端点、Dify应用、RAGFlow配置拆为子组件 | `features/admin/pages/AiAppManagementPage.jsx` (686行) |

### Phase 6: CI/CD 可靠性提升（中复杂度）

| 项目 | 描述 | 涉及文件 |
|------|------|----------|
| 启用 lint 阻断 | 移除 `continue-on-error: true` | `.github/workflows/ci.yml` |
| 添加前端安全检查 | 增加 `npm audit` 检查 | `.github/workflows/ci.yml` |
| 合并重复 CI | 统一 `ci.yml`, `ci-develop.yml`, `ci-test.yml` | `.github/workflows/` |

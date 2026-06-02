# 测试覆盖率提升至 80% 实施计划

**日期**: 2026-06-02
**目标**: 前后端测试覆盖率提升至 80% 以上

## 当前覆盖率

| 项目 | 当前状态 | 目标 |
|------|----------|------|
| 后端 (Django + pytest) | 约 55-65% (fail-under=70%) | 80%+ |
| 前端 (React + Jest) | Statements 23%, Branches 19%, Functions 23%, Lines 24% | 80%+ |

## Phase 1: 后端核心基础设施 (~105 用例) ✅ 已完成

- [x] users 模块 (29 测试通过) — serializer 边界、权限缓存、guest 关联
- [x] events 模块 (31 测试通过) — Schedule/Trial/ScheduleGenerator 全面覆盖
- [x] personnel 模块 (17 测试通过) — 加密字段、子资源 CRUD
- [x] documents 模块 (15 测试通过) — Book/Chapter/模板

## Phase 2: 后端核心业务模块 (~110 用例)

- [ ] compliance 模块 (~20) — ComplianceChecker service 层
- [ ] smart_assistant 模块 (~20) — 聊天流、知识库、LLM mock
- [ ] 次要模块批量 (~60) — meeting_rooms, news, notifications, sensor, permissions, config, external_integration, dashboard, llm_service, dify_apps, ragflow, office_assistant
- [ ] core 管理命令 (~15) — backup_db, check_migrations, list_versions

## Phase 3: 前端基础设施 (~30 用例)

- [ ] axiosConfig 全面测试 (~15) — Token 刷新、请求队列、401 处理
- [ ] AuthContext 补充测试 (~15) — guest 权限、pageConfig

## Phase 4: 前端批量补充 (~200+ 用例)

- [ ] API 层 (10 模块)
- [ ] 页面组件 (20+ 页面)
- [ ] 共享组件 (10+ 组件)
- [ ] Hooks (5 hooks)
- [ ] Utils & Context

## 配置调整

- 后端 pytest.ini: `--cov-fail-under` 70 → 80
- 前端 jest.config.js: 覆盖率阈值 50 → 65 → 80

# 测试覆盖率提升至 80% 实施计划

**日期**: 2026-06-02
**目标**: 前后端测试覆盖率提升至 80% 以上

## 当前覆盖率总览

| 项目 | 当前状态 | 目标 |
|------|----------|------|
| **后端 (Django + pytest)** | **85%** ✅ (554 passed, 2 failed) | 80%+ ✅ **已达标** |
| **前端 (React + Jest)** | Statements 21%, Branches 17%, Functions 21%, Lines 22% | 80%+ (进行中) |

**新增测试总计**: 148 个 (后端 139 + 前端 9) |

## Phase 1: 后端核心基础设施 (~105 用例) ✅ 已完成

- [x] users 模块 (29 测试通过) — serializer 边界、权限缓存、guest 关联
- [x] events 模块 (31 测试通过) — Schedule/Trial/ScheduleGenerator 全面覆盖
- [x] personnel 模块 (17 测试通过) — 加密字段、子资源 CRUD
- [x] documents 模块 (15 测试通过) — Book/Chapter/模板

## Phase 2: 后端核心业务模块 ✅ 已完成

- [x] compliance 模块 (18 测试通过) — ComplianceChecker service 层
- [x] smart_assistant 模块 (10 测试通过) — 聊天流、知识库、LLM mock
- [x] 次要模块批量 (18 测试通过) — meeting_rooms, news, notifications, sensor, permissions, config

## Phase 3: 前端基础设施 ✅ 已完成

- [x] AuthContext 补充测试 (9 测试通过) — login、logout、register、loginAsGuest、pageConfigs、guest 权限

## Phase 4: 前端批量补充 (~200+ 用例)

- [ ] API 层 (10 模块)
- [ ] 页面组件 (20+ 页面)
- [ ] 共享组件 (10+ 组件)
- [ ] Hooks (5 hooks)
- [ ] Utils & Context

## 配置调整

- 后端 pytest.ini: `--cov-fail-under` 70 → 80
- 前端 jest.config.js: 覆盖率阈值 50 → 65 → 80

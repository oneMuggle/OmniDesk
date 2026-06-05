# OmniDesk 技术手册

> 面向开发者的完整技术文档，涵盖架构、部署、API、各功能模块实现细节。

## 目录

### 基础设施

| 编号 | 文档 | 简介 |
|------|------|------|
| 01 | [架构总览](01-architecture-overview.md) | 项目整体架构、技术栈、目录结构 |
| 02 | [部署指南](02-deployment-guide.md) | Docker Compose 部署、离线部署、自动化部署 |
| 03 | [CI/CD 指南](03-cicd-guide.md) | GitHub Actions 持续集成与部署流程 |
| 04 | [测试策略](04-testing-strategy.md) | 开发期测试 + 部署期测试双体系 |
| 05 | [API 参考](05-api-reference.md) | 所有 REST API 端点完整参考 |
| 06 | [数据库模型](06-database-models.md) | Django 模型总览与关系图 |

### 功能模块

| 编号 | 文档 | 简介 |
|------|------|------|
| 07 | [用户与权限](07-user-permissions.md) | 后端角色授权 + 前端动态页面可见性 |
| 08 | [排班与试验](08-schedule-trial.md) | 排班管理、试验管理模块实现 |
| 09 | [会议室预约](09-meeting-room.md) | 会议室预约系统实现 |
| 10 | [传感器管理](10-sensor-management.md) | 传感器校准与管理模块 |
| 11 | [备忘录系统](11-memo-system.md) | 备忘录 CRUD 与分类系统 |
| 12 | [公告系统](12-announcement-system.md) | 公告发布与管理 |
| 13 | [新闻系统](13-news-system.md) | 新闻发布与管理模块 |
| 14 | [项目与合规](14-project-compliance.md) | 项目管理、合规追踪模块 |
| 15 | [用户交流模块](15-communication-module.md) | ⚠️ 前端未实现，仅后端 API |
| 16 | [智能助手系统](16-smart-assistant.md) | 智能助手系统架构与实现 |
| 17 | [AI 助手深化设计](17-ai-assistant-deep-design.md) | 多轮对话、工具链、模型降级、成本监控 |
| 18 | [外部集成架构](18-external-integration.md) | 🔄 进行中 |
| 19 | [版本管理系统](19-version-management.md) | 版本号、CHANGELOG、升级/回滚系统 |

### 专项主题

| 编号 | 文档 | 简介 |
|------|------|------|
| 20 | [桌面客户端](20-desktop-client.md) | 三部分架构中的桌面客户端实现 |
| 21 | [游客模式](21-guest-mode.md) | 游客模式设计与实现 |
| 22 | [Win7 兼容性](22-win7-compatibility.md) | Windows 7 / Chrome 109 兼容性方案 |
| 23 | [离线部署](23-offline-deployment.md) | 内网无外网环境部署指南,含三层一致性约束(2026-06 阶段 1-4 收尾) |
| 24 | [安全检查清单](24-security-checklist.md) | 6 个 CVE 详细分析 + OWASP Top 10 对照 |
| 25 | [API 性能审计](25-api-performance-audit.md) | 52 个 ViewSet 性能盘点 + 优化建议 |
| 26 | [人员-用户关联](26-personnel-user-association.md) | Personnel ↔ CustomUser 关联方案、字段权限、通知机制、link_user_personnel 命令(2026-06 v0.4.0) |

---

## 文档规范

- 技术手册采用"总览(本文件)+分章节"结构
- 每个章节独立成文，文件名格式 `XX-topic-name.md`
- 进行中的计划保留在项目根目录 `docs/plans/` 中
- 过时文档立即删除，不得保留历史版本

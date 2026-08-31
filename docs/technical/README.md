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
| 16 | [智能助手系统](16-smart-assistant.md) | 智能助手架构、13 工具、输出契约、Hooks、doctor 自检、晨报、会话 fork/导出、Office 文件附件能力（2026-08 阶段 1）、原生 Function Calling（L1 + L1.1 加固:流式 tool_calls / 结构化参数 / 写工具确认） |
| 17 | [AI 助手深化设计](17-ai-assistant-deep-design.md) | 多轮对话、工具链、模型降级、成本监控 |
| 18 | [外部集成架构](18-external-integration.md) | 🔄 进行中 |
| 19 | [版本管理系统](19-version-management.md) | 版本号、CHANGELOG、升级/回滚系统 |
| 35 | [通知中心](35-notifications.md) | 站内通知落库 + 轮询 API、类型/优先级/去重、信号触发(2026-08 R4-E5) |
| 36 | [文件处理](36-file-processing.md) | Office / PDF 上传、异步解析与 AI 分析(Processor 策略模式 + Celery 异步,2026-08 R4-E5) |
| 37 | [联培生管理](37-joint-students-module.md) | 联合培养硕博研究生档案、月度报告、A 档名额算法、月补助自动计算(后端完整 / 前端待补,2026-08-19 恢复) |

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
| 27 | [日志规范与事件清单](27-logging-standards.md) | 日志使用、事件清单、脱敏规范 |
| 28 | [智能助手覆盖率路线图](28-smart-assistant-coverage-roadmap.md) | smart_assistant 模块 63.25% → ≥85% 补齐方案、CI 守卫、+63 测试用例(2026-06 v0.6.0) |
| 29 | [性能 Profiling](29-performance-profiling.md) | django-silk dev 接入与使用 |
| 30 | [发布渠道机制](30-release-channels.md) | alpha/beta/preview/stable 4 段式发布渠道 + hotfix（含 main/beta/rc 自动同步机制）|
| 31 | [paperless-ngx 集成](31-paperless-integration.md) | paperless 集成架构、Outbox 写降级、联邦搜索、API、模型、部署、故障排查 |
| 32 | [Smart Assistant 多 Agent](32-smart-assistant-multi-agent.md) | MultiAgentExecutor / Pipeline / Fanout / Hierarchical + Hook 系统（v0.5.0 已实现） |
| 33 | [RAGFlow 集成](33-ragflow-integration.md) | RAGFlow API 客户端、Dataset/Chat 管理、docker-compose 部署、健康检查（v0.6.0-alpha.2 已实现） |
| 34 | [Smart Assistant 性能基准](34-smart-assistant-perf-benchmark.md) | P95 / 50 并发 / 缓存 TTFB 实测数据与优化手段（SAIS 分支 4 性能验收） |
| 38 | [LLM 服务层](38-llm-service.md) | 多端点 LLM 路由器:DB LlmAppConfig 降级 → Ollama 本地兜底、usage 成本核算、工具调用(2026-08 R4-E5) |
| 39 | [可观测性](39-observability.md) | 统一 logger、事件常量、request_id HTTP / Celery 全链路传播、SafeTextFormatter(2026-08 R4-E5) |
| 40 | [冒烟测试覆盖矩阵](40-smoke-test-coverage.md) | smoke_tests.sh 阶段 1-11 覆盖清单、app 端点 GET 探针表、已知缺口 |
| 41 | [2026-07 安全/数据 P0 批次审计](41-p0-security-data-safety-batch-2026-07.md) | 12 项 P0 安全与数据安全修复的实施轨迹、commit 索引、CI 验收、风险评估与回滚方案 |
| 42 | [channel-sync 远程分支自动清理](42-channel-sync-branch-cleanup.md) | cron 清理 `channel-sync/*` 归档分支、commit ≥14 天规则、豁免清单维护、误删恢复(2026-08) |
| 43 | [智能助手多智能体协作卡片](43-smart-assistant-collab-card.md) | ✅ 已完成：消费真实 Celery AgentTask/AgentEvent SSE，支持真实工具执行、`last_seq` 断点续传、paused/partial/failed 状态、旧版浏览器 timeline 降级（不改变 React 18 对 IE11 的整体不支持）、审计 JSON、AgentWriteLog 回滚与站内通知；8 个场景仅作示例入口 |

### 新增功能点(待建章节预留编号)

| 编号 | 主题 | 计划来源 |
|------|------|----------|
| 37 | 联培生管理 (joint_students app) | 设计草案见 [superpowers 计划](../superpowers/specs/2026-07-28-联培生管理模块-design.md) |

---

## 文档规范

- 技术手册采用"总览(本文件)+分章节"结构
- 每个章节独立成文，文件名格式 `XX-topic-name.md`
- 进行中的计划保留在项目根目录 `docs/plans/` 中
- 过时文档立即删除，不得保留历史版本

> 📅 最近更新:2026-08-09 — 第 16 章同步 L1.1 原生 Function Calling 加固(流式原生 tool_calls / 结构化参数透传 / 写工具确认 ConfirmationHook),§13 新增 §13.6 小节、§2.10 Hook 表新增 ConfirmationHook 并修正接线现状;2026-08-06 曾归档 2026-08 阶段 1(智能助手 chat 支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv 上传 + OfficeExtractor 抽取 + OfficeRead/OfficeGenerate/Spreadsheet 三件套 + 下载卡片)。

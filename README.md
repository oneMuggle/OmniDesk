# OmniDesk: 集成化业务管理平台

> 全栈业务管理平台(Django 4.2 + React 18 + Vite 5)。面向组织级场景,覆盖排班、试验、会议室、传感器、备忘录、公告、新闻、项目、合规、人员、智能助手、AI 应用、文档库与发布管理。
> 当前版本: `0.7.0-alpha.2`(alpha 渠道)

## 项目特性

OmniDesk 提供以下能力,均开箱即用,支持内网/离线部署:

### 业务模块
| 模块 | 说明 |
|------|------|
| **排班管理** | 周/月排班视图、试验关联、人员冲突检测 |
| **试验管理** | 试验全生命周期、阶段流转、合规校验 |
| **会议室预约** | 实时占用图、冲突检测、审批 |
| **传感器管理** | 设备校准、历史读数、阈值告警 |
| **备忘录** | 个人/共享备忘、提醒、分类 |
| **公告 / 新闻** | 多级发布、已读追踪、置顶 |
| **项目管理** | 项目台账、阶段、文档关联 |
| **合规追踪** | 合规事项、责任人、到期提醒 |
| **人员-用户关联** | 员工档案绑定登录账号,自动同步 |
| **积分管理** | 员工积分、兑换、核销 |

### AI 与知识
| 模块 | 说明 |
|------|------|
| **智能助手** | 多 Agent 协作、13+ 工具、Hooks 自检、晨报、会话 fork/导出、性能基准(技术手册第 16/32/34 章) |
| **AI 能力展示** | 工具列表、调用样例、实时演示 |
| **Office 助手 / 文件分析** | Office 文件智能解析(MinerU 集成)与内容检索 |
| **Dify 应用** | 与 Dify 平台对接,一键运行聊天型 AI 应用 |
| **RAGFlow 集成** | Dataset/Chat 管理、API 客户端、健康检查(技术手册第 33 章) |
| **知识库管理** | 文档分段、向量化、人工维护 |
| **联邦搜索** | 顶部全局搜索同时查业务数据 + paperless 全文 |

### 平台与集成
| 模块 | 说明 |
|------|------|
| **文档库 (paperless-ngx 集成)** | 业务附件统一落盘到 paperless,Outbox 降级,联邦搜索高亮,5 种同步状态可视化(技术手册第 31 章) |
| **桌面客户端** | 三层架构中的桌面端(技术手册第 20 章) |
| **集成中心 / 快捷外链 / 插件市场** | 控制面板的扩展入口,统一管理 SSO、外部跳转、自定义插件 |
| **通知中心** | 站内通知 + 邮件 + Webhook,支持分组与已读追踪 |
| **仪表盘** | 个人首页:日程、待办、未读通知、最新公告 |
| **版本管理与发布渠道** | 4 段式渠道 alpha/beta/preview/stable + hotfix,配套备份/回滚(技术手册第 19/30 章) |

## 项目结构

```
OmniDesk/
├── omni_desk_backend/          # Django 后端(约 30 个 apps)
├── omni_desk_frontend/         # React 前端(Vite 5,约 25 个 features)
├── deployment/docker/          # Docker Compose + 离线包打包脚本
├── docs/                       # 全部项目文档(技术手册、用户手册、计划)
├── utils/                      # 工具脚本
└── README.md                   # 本文件
```

### 后端 Apps(Django INSTALLED_APPS)

`personnel`, `users`, `events`, `documents`, `config`, `memos`, `dify_apps`,
`office_assistant`, `projects`, `compliance`, `ragflow_service`, `meeting_rooms`,
`sensor_management`, `communication`, `news`, `permissions`, `ebooks`,
`smart_assistant`, `core`, `notifications`, `dashboard`, `external_integration`,
`paperless_proxy`, `search_federation`, `file_processing`, `llm_service`
+ Django 标准库 + DRF + SimpleJWT + Celery Beat。

自定义用户模型: `AUTH_USER_MODEL = 'users.CustomUser'`

### 前端 features

`admin`, `announcements`, `auth`, `communication`, `compliance`, `dify-apps`,
`documents`, `documents-library`, `ebook`, `equipment`, `external-links`,
`integration-hub`, `meeting-room`, `memo`, `news`, `notifications`,
`office-assistant`, `personnel`, `plugin-market`, `profile`, `projects`,
`schedule`, `search-federation`, `sensor`, `smart-assistant`, `system`, `user`
共 29 个受保护页面(见 `omni_desk_frontend/public/routes.json`)。

## 先决条件

- **Python 3.10**(与 Dockerfile、CI、conda 环境统一)
- **Node.js 18+**(Vite 5 要求)
- **PostgreSQL 13+** 与 **Redis 6+**(Celery 任务、缓存依赖)
- **Docker / Docker Compose**(生产 / 离线部署;dev 也可绕过)
- **Conda 环境**:`omni_desk`(避免污染 base)

> ⚠️ 项目对 Windows 7 + Chrome 109 浏览器做了兼容性测试(技术手册第 22 章)。
> 离线/内网部署约束见技术手册第 23 章。

## 快速开始(开发环境)

### 一、环境准备

```bash
# 创建并激活 conda 环境(Python 3.10)
conda create -n omni_desk python=3.10 -y
conda activate omni_desk

# 克隆仓库
git clone <repo-url> OmniDesk
cd OmniDesk
```

### 二、后端

```bash
cd omni_desk_backend

# 编译依赖(NEVER edit .txt 文件)
pip-compile -o requirements-prod.txt requirements.in
pip-compile -o requirements.txt requirements-dev.in

# 安装
pip install -r requirements.txt

# 配置 .env(参考 settings/local.py 默认配置)

# 迁移 + 启动
python manage.py migrate
python manage.py runserver         # 默认使用 settings.local
```

后端默认监听 `http://127.0.0.1:8000`,登录入口 `/api/auth/login/`。

### 三、前端

```bash
cd omni_desk_frontend
npm install
npm start          # 监听 0.0.0.0:3000,Vite 代理 /api 到 8000
```

前端默认监听 `http://localhost:3000`。

## 测试

### 单元 / 集成(开发期)

```bash
# 后端(in-memory SQLite)
cd omni_desk_backend
pytest --ds=omni_desk_backend.settings.test

# 前端(Jest + RTL)
cd omni_desk_frontend
npm run test:coverage
```

> CI 守卫: 后端覆盖率红线 80%、前端 80%、mypy strict、ruff、ESLint。详见 [CI/CD 指南](docs/technical/03-cicd-guide.md)。

### 部署期(冒烟 / 集成)

- `deployment/docker/deploy_tests.sh`(可选 4 种 profile)
- `omni_desk_backend/conftest.py` + 各 `*tests*/test_*.py`

## 部署

### 推荐流程(按发布渠道)

```
main(开发合并) → 切 alpha 分支 → 内部 alpha 验证
   ↓
beta(公测) → 客户 preview 验证
   ↓
rc → stable(发布 GA)
```

详细规范与脚本: [发布渠道机制](docs/technical/30-release-channels.md) 和 [CI/CD 指南](docs/technical/03-cicd-guide.md)。

### Docker Compose

```bash
cd deployment/docker

# 部署脚本
./deploy_docker.sh up              # 启动
./deploy_docker.sh down            # 停止
./deploy_docker.sh logs [service]  # 日志
./deploy_docker.sh migrate         # 迁移
./deploy_docker.sh collectstatic   # 收集静态
```

完整步骤见 [部署指南](docs/technical/02-deployment-guide.md)。

### 离线 / 内网

```bash
# 1. 在外网机器打包镜像
cd deployment/docker
./build_and_export.sh

# 2. 拷贝到内网机器

# 3. 内网机器部署
./deploy_offline.sh up
```

离线包目录命名遵循 `omnidesk-offline-<channel>-v<version>/`,含 `BUILD-MANIFEST.json`(channel 字段)。

### 升级与回滚

```bash
# 升级(带 10 步安全门禁:检查 → 加载镜像 → 预检迁移 → 确认 → 备份 → 更新 → 迁移 → 健康检查)
./upgrade.sh v0.7.0

# 回滚(同时回滚镜像 + 可选 DB restore)
./rollback.sh v0.6.3 [--restore-db backup.sql.gz]
```

完整流程、数据安全保证、备份策略见:
- [部署指南 § 部署运维](docs/technical/02-deployment-guide.md)
- [CI/CD 指南 § 离线升级与数据安全](docs/technical/03-cicd-guide.md)
- [版本管理系统](docs/technical/19-version-management.md)

## 文档

| 类型 | 入口 | 目标读者 |
|------|------|----------|
| 技术手册 | [docs/technical/](docs/technical/README.md) | 开发者(架构、API、部署、模块设计) |
| 用户手册 | [docs/user-manual/](docs/user-manual/README.md) | 最终用户(功能说明、操作步骤) |
| 实施计划 | [docs/plans/](docs/plans/) | 进行中的功能设计稿(完成后并入手册或删除) |
| 项目规范 | [CLAUDE.md](CLAUDE.md) | AI Agent 与协作开发者(架构、约定、工作流) |
| Agent 详细指令 | [AGENTS.md](AGENTS.md) | AI Agent 工作细则 |

## 贡献与开发

### 工作流

1. 切 feature 分支(详见 [CLAUDE.md](CLAUDE.md))
2. 提交前 checklist:
   - [ ] `pytest`(后端单测与覆盖率)
   - [ ] `npm run test:coverage`(前端)
   - [ ] `ruff check`(后端 lint)
   - [ ] `mypy`(类型检查)
   - [ ] 更新相关 docs(/technical 或 /user-manual)

### 提交规范

Conventional Commits:`feat:` / `fix:` / `refactor:` / `perf:` / `docs:` / `test:` / `chore:` / `ci:` / `build:`

主分支(`main`)受保护,所有改动通过 PR 合并。

## 联系方式

项目维护者: 见仓库的 CODEOWNERS / 团队通讯录
- 问题反馈: 提交 Issue
- 安全问题: 走内部渠道(参见 [安全检查清单](docs/technical/24-security-checklist.md))

---

> 📅 最近更新: 2026-07-29 — 同步 0.7.0-alpha.2 渠道功能(RAGFlow、文档库、智能助手多 Agent、文件分析、发布渠道、升级/回滚)。

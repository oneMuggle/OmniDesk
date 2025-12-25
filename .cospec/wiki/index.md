# OmniDesk 项目技术文档索引

## 📚 文档导航

本索引为AI提供OmniDesk项目的完整技术文档导航，支持快速信息定位和上下文理解。

### 📋 项目概述

**项目定位**: 一个全栈业务管理平台，旨在简化文档、项目、传感器和用户管理等组织运营。
**技术栈**: 后端(Django, DRF, Celery), 前端(React, MUI), 数据库(PostgreSQL, Redis)。
**架构特点**: 前后端分离的模块化单体架构，通过Docker容器化部署，并由Nginx代理。

### 🏗️ 组织结构

```
omni_desk_backend/
├── users/            # 用户、认证、权限
├── personnel/        # 人事信息管理
├── projects/         # 项目管理
├── documents/        # 文档与书籍管理
├── sensor_management/ # 传感器管理
└── omni_desk_backend/ # Django项目配置
omni_desk_frontend/
├── src/
│   ├── features/     # 按功能划分的模块
│   │   ├── auth/
│   │   ├── projects/
│   │   └── ...
│   ├── shared/       # 共享组件、上下文
│   └── routes/       # 路由配置
deployment/
├── docker/           # Docker部署相关
└── ...
```

### 🎯 核心文档概览

| 文档名称 | 文件路径 | 主要内容 | 适用场景 |
|---|---|---|---|
| **项目概览** | [`01_Overview.md`](.cospec/wiki/01_Overview.md) | 项目定位、技术栈、架构特色和开发规范。 | 项目理解、技术选型、功能开发 |
| **整体架构** | [`02_Architecture.md`](.cospec/wiki/02_Architecture.md) | 模块化单体架构，分层设计和部署拓扑。 | 架构设计、模块开发、系统集成 |
| **服务依赖** | [`03_Service_Dependencies.md`](.cospec/wiki/03_Service_Dependencies.md) | 前后端、异步任务及基础设施间的依赖关系。 | 依赖管理、性能优化、故障排查 |
| **数据流分析** | [`04_Data_Flow_and_Integration.md`](.cospec/wiki/04_Data_Flow_and_Integration.md) | 同步API调用和异步Celery任务的数据流转。 | 数据处理、集成开发、性能调优 |
| **服务模块** | [`05_*.md`](.cospec/wiki/05_Module_Users.md) | `users`, `projects`等核心模块的功能、API和数据模型。 | 服务开发、代码重构、功能扩展 |
| **数据库分析** | [`06_Database_Schema.md`](.cospec/wiki/06_Database_Schema.md) | 基于Django模型的PostgreSQL表结构和关系。 | 数据库设计、查询优化、数据迁移 |
| **API接口** | [`07_API_Analysis.md`](.cospec/wiki/07_API_Analysis.md) | 基于DRF的RESTful API设计，JWT认证。 | API开发、接口测试、集成开发 |
| **部署分析** | [`08_Deployment.md`](.cospec/wiki/08_Deployment.md) | 基于Docker和GitHub Actions的CI/CD流程。 | 部署配置、运维管理、扩容缩容 |
| **开发测试** | [`09_Dev_and_Test.md`](.cospec/wiki/09_Dev_and_Test.md) | 基于Docker Compose的开发环境和Pytest/Jest测试。 | 环境搭建、本地开发、编写测试 |

### 🚀 角色导向导航

#### 🆕 新手入门路径
1. **快速了解项目**: [`项目概览`](.cospec/wiki/01_Overview.md) → [`API接口`](.cospec/wiki/07_API_Analysis.md)
2. **开发环境准备**: [`开发测试`](.cospec/wiki/09_Dev_and_Test.md) → [`部署分析`](.cospec/wiki/08_Deployment.md)

#### 🏗️ 架构设计路径
1. **架构理解**: [`整体架构`](.cospec/wiki/02_Architecture.md) → [`服务依赖`](.cospec/wiki/03_Service_Dependencies.md)
2. **数据架构**: [`数据流分析`](.cospec/wiki/04_Data_Flow_and_Integration.md) → [`数据库分析`](.cospec/wiki/06_Database_Schema.md)

#### 💻 开发实施路径
1. **编码规范**: [`项目概览`](.cospec/wiki/01_Overview.md) → [`服务模块`](.cospec/wiki/05_Module_Users.md)
2. **接口开发**: [`API接口`](.cospec/wiki/07_API_Analysis.md) → [`数据库分析`](.cospec/wiki/06_Database_Schema.md)

#### 🔧 运维部署路径
1. **部署配置**: [`部署分析`](.cospec/wiki/08_Deployment.md) → [`服务依赖`](.cospec/wiki/03_Service_Dependencies.md)
2. **系统维护**: [`整体架构`](.cospec/wiki/02_Architecture.md) → [`数据流分析`](.cospec/wiki/04_Data_Flow_and_Integration.md)
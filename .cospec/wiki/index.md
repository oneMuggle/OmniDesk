# OmniDesk 项目技术文档索引

## 📚 文档导航

本索引为AI提供OmniDesk项目的完整技术文档导航，支持快速信息定位和上下文理解。

### 📋 项目概述

**项目定位**: 一个全栈集成化业务管理平台，旨在简化组织运营，提供统一的解决方案。
**技术栈**: 后端Django (Python)，前端React (JavaScript)，数据库PostgreSQL，缓存Redis。
**架构特点**: 采用前后端分离的模块化单体架构，通过Docker容器化部署，并使用GitHub Actions实现CI/CD。

### 🏗️ 组织结构

```
omni_desk_backend/  # 后端 Django 应用
├── events/         # 日程、排班、公告等模块
├── personnel/      # 人事信息管理模块
├── projects/       # 项目管理模块
├── users/          # 用户、认证、权限模块
├── llm_service/    # AI大模型服务客户端
└── ...
omni_desk_frontend/ # 前端 React 应用
├── src/
│   ├── api/        # API请求封装
│   ├── components/ # 可复用UI组件
│   ├── pages/      # 页面级组件
│   └── ...
deployment/         # 部署脚本和配置
├── docker/
└── source/
docs/               # 项目文档
.github/            # CI/CD 工作流
...
```

### 🎯 核心文档概览

| 文档名称 | 文件路径 | 主要内容 | 适用场景 |
|---|---|---|---|
| **项目概览** | [`01_Overview.md`](.cospec\wiki\01_Overview.md) | 项目定位、核心价值、技术栈、架构特色。 | 项目理解、技术选型、功能开发 |
| **整体架构** | [`02_Architecture.md`](.cospec\wiki\02_Architecture.md) | 模块化单体架构，前后端分离，分层设计。 | 架构设计、模块开发、系统集成 |
| **服务依赖** | [`03_Service_Dependencies.md`](.cospec\wiki\03_Service_Dependencies.md) | 内部模块依赖、对数据库和缓存的强依赖。 | 依赖管理、性能优化、故障排查 |
| **数据流分析** | [`04_Data_Flow_and_Integration.md`](.cospec\wiki\04_Data_Flow_and_Integration.md) | 同步业务流、异步任务流和API集成模式。 | 数据处理、集成开发、性能调优 |
| **服务模块** | [`05_Service_Module_Analysis.md`](.cospec\wiki\05_Service_Module_Analysis.md) | `users`和`events`等核心模块的功能与API。 | 服务开发、代码重构、功能扩展 |
| **数据库分析** | [`06_Database_Schema_Analysis.md`](.cospec\wiki\06_Database_Schema_Analysis.md) | 共享数据库模式，核心表结构与关系。 | 数据库设计、查询优化、数据迁移 |
| **API接口** | [`07_API_Interface_Analysis.md`](.cospec\wiki\07_API_Interface_Analysis.md) | RESTful API设计，JWT认证，统一错误处理。 | API开发、接口测试、集成开发 |
| **部署分析** | [`08_Deployment_Analysis.md`](.cospec\wiki\08_Deployment_Analysis.md) | 容器化部署，GitHub Actions CI/CD流程。 | 部署配置、运维管理、扩容缩容 |
| **开发测试** | [`09_Develop_Test_Analysis.md`](.cospec\wiki\09_Develop_Test_Analysis.md) | 前后端分离的启动与调试，Pytest与Jest测试。 | 环境搭建、本地开发、编写测试 |

### 🚀 角色导向导航

#### 🆕 新手入门路径
1. **快速了解项目**: [`项目概览`](.cospec\wiki\01_Overview.md) → [`API接口`](.cospec\wiki\07_API_Interface_Analysis.md)
2. **开发环境准备**: [`开发测试`](.cospec\wiki\09_Develop_Test_Analysis.md) → [`部署分析`](.cospec\wiki\08_Deployment_Analysis.md)

#### 🏗️ 架构设计路径
1. **架构理解**: [`整体架构`](.cospec\wiki\02_Architecture.md) → [`服务依赖`](.cospec\wiki\03_Service_Dependencies.md)
2. **数据架构**: [`数据流分析`](.cospec\wiki\04_Data_Flow_and_Integration.md) → [`数据库分析`](.cospec\wiki\06_Database_Schema_Analysis.md)

#### 💻 开发实施路径
1. **模块与接口**: [`服务模块`](.cospec\wiki\05_Service_Module_Analysis.md) → [`API接口`](.cospec\wiki\07_API_Interface_Analysis.md)
2. **数据与测试**: [`数据库分析`](.cospec\wiki\06_Database_Schema_Analysis.md) → [`开发测试`](.cospec\wiki\09_Develop_Test_Analysis.md)

#### 🔧 运维部署路径
1. **部署配置**: [`部署分析`](.cospec\wiki\08_Deployment_Analysis.md) → [`服务依赖`](.cospec\wiki\03_Service_Dependencies.md)
2. **系统维护**: [`整体架构`](.cospec\wiki\02_Architecture.md) → [`数据流分析`](.cospec\wiki\04_Data_Flow_and_Integration.md)
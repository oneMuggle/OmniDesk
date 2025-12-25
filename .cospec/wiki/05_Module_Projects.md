# 服务模块分析: projects

## 模块概述
- **模块名称**: `projects`
- **模块描述**: 负责OmniDesk平台中的项目管理功能。提供项目的创建、查询、更新和删除等核心业务操作。
- **技术栈**: Django, Django Rest Framework
- **部署方式**: 作为 `omni_desk_backend` 单体服务的一部分进行部署。

## 核心功能
| 功能 | 描述 | 业务价值 |
|---|---|---|
| **项目管理** | 提供完整的CRUD（创建、读取、更新、删除）功能来管理项目生命周期。 | 平台的核心业务功能之一，用于跟踪和管理组织内的各项事务。 |
| **权限控制** | 基于用户的角色（管理员、经理）来控制对项目的访问和操作权限。 | 保证项目信息的安全性和完整性，确保只有授权人员才能管理项目。 |
| **项目查询** | 允许管理员查看所有项目，允许项目经理查看自己负责的项目。 | 提供不同角色的数据视图，满足不同管理层级的需求。 |

## 接口分析 (REST API)
`projects` 模块使用Django Rest Framework的`ModelViewSet`和`DefaultRouter`，自动生成了一套标准的RESTful API。
- **基本路径**: `/api/projects/`

| 接口路径 | HTTP方法 | 功能描述 | 权限要求 |
|---|---|---|---|
| `/api/projects/` | `GET` | 获取项目列表。管理员看到所有项目，经理看到自己管理的项目。 | `IsAuthenticated` |
| `/api/projects/` | `POST` | 创建一个新项目。仅限管理员和经理。 | `IsAuthenticated`, `IsProjectOwnerOrAdmin` |
| `/api/projects/{id}/` | `GET` | 获取单个项目的详细信息。 | `IsAuthenticated`, `IsProjectOwnerOrAdmin` |
| `/api/projects/{id}/` | `PUT`, `PATCH` | 更新一个项目的信息。 | `IsAuthenticated`, `IsProjectOwnerOrAdmin` |
| `/api/projects/{id}/` | `DELETE` | 删除一个项目。 | `IsAuthenticated`, `IsProjectOwnerOrAdmin` |

## 数据模型分析

### `Project` 模型
- **描述**: 这是`projects`模块唯一的核心数据模型，用于表示一个项目。
- **关键字段**:
    - `name`: 项目名称，唯一。
    - `description`: 项目的详细描述。
    - `start_date`, `end_date`: 项目的起止日期。
    - `manager`: `ForeignKey` 关联到`CustomUser`模型，表示该项目的负责人。
    - `status`: 项目的当前状态（如：进行中, 已完成等）。
- **关系**: 与`users.CustomUser`是多对一关系（一个用户可以管理多个项目）。

## 模块依赖分析

### 内部依赖
- **`users` 模块**: `Project`模型的`manager`字段直接外键关联到`users.CustomUser`模型。该模块的权限系统也依赖于用户的角色（是否为管理员、经理）。这是一个强依赖。

### 外部库依赖
- **`djangorestframework`**: 用于快速构建`ModelViewSet`和序列化器。

### 基础设施依赖
- **PostgreSQL**: `Project`模型的数据存储在PostgreSQL中。

## 安全分析
- **认证**: 继承自DRF的全局配置，所有接口都需要通过JWT认证 (`permissions.IsAuthenticated`)。
- **授权**: 
    - 模块内定义了自定义权限类`IsProjectOwnerOrAdmin`。
    - 这个权限类确保了只有项目的负责人(`manager`)或管理员才能编辑或删除项目。
    - 在获取项目列表（`get_queryset`）和创建项目（`perform_create`）的方法中，有明确的业务逻辑来根据用户的角色（管理员、经理）返回不同的数据或执行不同的操作。这种在视图层实现的权限控制非常具体和有效。

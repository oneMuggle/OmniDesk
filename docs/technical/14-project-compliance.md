# 技术文档：项目资料管理

## 1. 概述

项目资料管理模块旨在为所有文档、资料和合规性问题提供一个统一的、以项目为核心的组织框架。用户可以创建和管理项目，并将相关的文档和发现的合规问题归属到特定的项目中，从而实现项目档案的集中管理。

---

## 2. 后端实现

### 2.1. `projects` 应用

这是项目管理功能的核心应用。

- **数据模型**: [`omni_desk_backend/projects/models.py`](omni_desk_backend/projects/models.py:4)
  - `Project`: 定义了一个项目实体，包含名称、描述、起止日期、项目负责人 (`manager`) 和状态等关键字段。

- **API 视图**: [`omni_desk_backend/projects/views.py`](omni_desk_backend/projects/views.py:5)
  - `ProjectViewSet`: 提供对 `Project` 模型的完整CRUD操作。
  - **端点**: `/api/projects/`
  - **权限**:
    - 所有经过身份验证的用户都可以访问。
    - 管理员 (`is_staff`) 可以查看所有项目。
    - 普通用户只能查看自己作为 `manager` 的项目。
    - 创建项目时，若未指定 `manager`，则默认为当前请求的用户。

### 2.2. `compliance` 应用

此应用用于跟踪和管理与项目文档相关的合规性问题。

- **数据模型**: [`omni_desk_backend/compliance/models.py`](omni_desk_backend/compliance/models.py:6)
  - `ComplianceIssue`: 定义了一个合规问题实体。
  - **核心关联**:
    - `project`: 外键，强制将每个合规问题关联到一个 `Project`。
    - `document_book`: 外键（可选），关联到 `documents.Book`。
    - `document_template`: 外键（可选），关联到 `documents.DocumentTemplate`。
  - 包含问题类型、描述、位置、状态、严重程度和截止日期等字段。

- **API 视图**: [`omni_desk_backend/compliance/views.py`](omni_desk_backend/compliance/views.py:13)
  - `ComplianceIssueViewSet`: 提供对 `ComplianceIssue` 模型的完整CRUD操作。
  - **端点**: `/api/compliance/issues/` (假设的URL，需要根据主 `urls.py` 确认)
  - **权限**:
    - 管理员可以访问所有问题。
    - 普通用户只能访问其负责项目下的问题。
    - 用户只能在自己负责的项目下创建、修改或删除问题。
  - **自定义API**:
    - `unread_count`: 一个 `GET` 方法的自定义端点，用于返回当前用户未处理的合规问题数量。

### 2.3. `documents` 应用集成

项目概念被集成到了现有的文档模型中。

- **数据模型**: [`omni_desk_backend/documents/models.py`](omni_desk_backend/documents/models.py)
  - `Book` 和 `DocumentTemplate` 模型都增加了一个外键字段 `project`，允许将每一份文档资料归属到一个具体的项目中。

---

## 3. 前端实现

前端通过与上述后端API交互，为用户提供了项目管理和浏览的操作界面。

- **项目管理页面** (例如 `ProjectsPage.jsx`):
  - 提供项目列表的展示、创建新项目和编辑现有项目的功能。
  - 用户可以从项目列表导航到项目详情页。

- **项目详情页**:
  - 集中展示一个特定项目的所有相关信息，包括其下的所有文档 (`Book`, `DocumentTemplate`) 和所有合规问题 (`ComplianceIssue`)。

- **文档和合规列表页**:
  - 在原有的文档列表和合规问题列表页面上，增加了按项目进行筛选的功能。
  - 在列表项中明确显示每个文档或问题所属的项目。

---

## 4. 待确认的功能

根据规划文档，以下功能在当前已分析的代码中未找到明确的实现，可能尚未开发或在其他模块中：

- **智能分析与查漏补缺**: 利用LLM（如Ollama）对文档内容进行智能分析以自动生成 `ComplianceIssue` 的具体实现。
- **定时提醒**: 利用Celery等任务队列对 `ComplianceIssue` 的截止日期进行定时检查和提醒的实现。
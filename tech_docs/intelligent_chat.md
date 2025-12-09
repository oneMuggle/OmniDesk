# 技术文档：智能问答系统

## 1. 概述

智能问答系统旨在集成多个第三方AI聊天服务，为用户提供一个统一的、可切换的问答入口。系统目前规划或已实现了对 Dify 和 Ragflow 两种服务的集成，它们采用了截然不同的技术方案。

---

## 2. Dify 集成 (IFrame 嵌入)

Dify 服务的集成采用了前端 IFrame 嵌入的方式，后端仅作为配置中心。

### 2.1. 后端实现 (`dify_apps` 应用)

- **数据模型**: [`omni_desk_backend/dify_apps/models.py`](omni_desk_backend/dify_apps/models.py:5)
  - `DifyApp`: 定义了一个 Dify 应用实体。
  - **核心字段**: `embed_url`。此字段存储了 Dify 应用的公开嵌入链接，是实现前端嵌入的关键。
  - 其他字段如 `name`, `description` 用于在后台进行管理和区分。

- **API 视图**: [`omni_desk_backend/dify_apps/views.py`](omni_desk_backend/dify_apps/views.py:8)
  - `DifyAppViewSet`: 提供对 `DifyApp` 模型的 CRUD 操作。
  - **功能**: 其主要目的是让管理员能够通过后台管理界面，动态地添加、修改或删除可供前端展示的 Dify 应用，而无需修改前端代码。

### 2.2. 前端实现

- 前端通过调用 `/api/dify-apps/` 获取所有激活的 Dify 应用列表。
- 用户选择一个 Dify 应用后，前端会获取其 `embed_url`，并将这个 URL 作为一个 `<iframe>` 元素的 `src` 属性，从而将 Dify 的聊天界面无缝嵌入到当前页面中。

---

## 3. Ragflow 集成 (后端代理)

Ragflow 服务的集成采用了后端 API 代理的模式，以保护 API Key 等敏感信息不暴露在前端。

### 3.1. 后端实现 (`ragflow_service` 应用)

- **数据模型**: [`omni_desk_backend/ragflow_service/models.py`](omni_desk_backend/ragflow_service/models.py:3)
  - `RagflowConfig`: 定义了一个 Ragflow 服务配置实体。
  - **核心字段**: `api_endpoint` 和 `api_key`。这些信息由后端存储和使用，绝不泄露给前端。

- **API 视图**: [`omni_desk_backend/ragflow_service/views.py`](omni_desk_backend/ragflow_service/views.py:9)
  - `RagflowConfigViewSet`: 提供对 `RagflowConfig` 模型的 CRUD 操作，用于后台管理。
  - **`query` (自定义 Action)**: 这是实现代理的核心。
    - **端点**: `POST /api/ragflow-service/configs/{pk}/query/`
    - **功能**:
      1.  前端将用户的提问（`question`）和会话ID（`conversation_id`）发送到此端点。
      2.  后端从数据库中加载对应的 `RagflowConfig`，获取其 `api_endpoint` 和 `api_key`。
      3.  后端使用 `requests` 库，构造一个符合 Ragflow API 规范的请求，并将问题转发到 Ragflow 的真实服务器。
      4.  后端接收到 Ragflow 服务器的响应后，再将其原封不动地返回给前端。

### 3.2. 前端实现

- 前端需要实现一个聊天界面。
- 当用户发送消息时，前端不是直接请求 Ragflow API，而是向后端的代理端点（`query` action）发送请求。
- 这种模式的优点是前端代码中完全不涉及敏感的 `api_key`，提高了安全性。

---

## 4. 统一入口（规划）

根据设计规划，最终目标是提供一个统一的智能问答页面，允许用户在不同的服务（如 Dify, Ragflow, DeepSeek）之间进行选择和切换。这需要前端进行相应的改造，例如：

- 提供一个服务选择器（如下拉菜单或标签页）。
- 根据用户的选择，动态地渲染 IFrame (Dify) 或调用不同的后端代理API (Ragflow, DeepSeek)。
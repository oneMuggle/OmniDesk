# 技术文档：新闻发布系统

## 1. 概述

新闻发布系统是一个用于管理和展示外部新闻链接的功能模块。它允许管理员对新闻进行分类，并记录每条新闻的标题、链接、发布日期以及相关的内部人员。系统还提供了基础的统计功能。该功能由一个独立的 `news` Django 应用提供支持。

---

## 2. 后端实现 (`news` 应用)

### 2.1. 数据模型

- **`NewsType`**: [`omni_desk_backend/news/models.py`](omni_desk_backend/news/models.py:4)
  - 用于定义新闻的分类，例如“公司新闻”、“行业动态”等。
  - 核心字段: `name` (分类名称)。

- **`NewsArticle`**: [`omni_desk_backend/news/models.py`](omni_desk_backend/news/models.py:10)
  - 记录了每一条新闻条目。
  - **核心字段**:
    - `title`: 新闻标题。
    - `link`: 指向原始新闻的URL。
    - `publication_date`: 新闻的发布日期。
    - `personnel`: 外键，关联到 `CustomUser` 模型，用于记录与此新闻相关的内部人员。
    - `news_type`: 外键，关联到 `NewsType`，实现新闻分类。

### 2.2. API 视图

- **`NewsTypeViewSet`**: [`omni_desk_backend/news/views.py`](omni_desk_backend/news/views.py:9)
  - 提供对 `NewsType` 模型的完整CRUD操作。
  - **端点**: `/api/news/news-types/`

- **`NewsArticleViewSet`**: [`omni_desk_backend/news/views.py`](omni_desk_backend/news/views.py:13)
  - 提供对 `NewsArticle` 模型的完整CRUD操作。
  - **端点**: `/api/news/news-articles/`
  - **查询与筛选**: `get_queryset` 方法被重写，以支持通过查询参数进行筛选：
    - `personnel_id`: 按关联人员ID筛选。
    - `month` (格式 `YYYY-MM`): 按发布月份筛选。
    - `type_id`: 按新闻类型ID筛选。

- **`NewsStatsView`**: [`omni_desk_backend/news/views.py`](omni_desk_backend/news/views.py:35)
  - 一个只读的 `APIView`，用于提供新闻发布的统计数据。
  - **端点**: `/api/news/news-stats/`
  - **功能**: 返回一个包含以下信息的JSON对象：
    - `total_articles`: 系统中新闻的总数。
    - `by_person`: 一个对象，按人员（用户名）组织数据，包含该人员的总发文数 (`total`) 和按月分的详细发文数 (`monthly`)。

### 2.3. URL 路由

- [`omni_desk_backend/news/urls.py`](omni_desk_backend/news/urls.py) 文件为上述所有 `ViewSet` 和 `APIView` 注册了相应的API端点，并通过主 `urls.py` 文件以 `/api/news/` 为前缀暴露给前端。

---

## 3. 前端实现

前端部分虽然没有详细探查，但其实现可根据后端API推断：

- **新闻管理页面**:
  - 一个管理界面，允许授权用户创建、编辑和删除 `NewsArticle` 和 `NewsType`。
  - 包含筛选控件，允许用户按人员、月份或类型查看新闻列表。

- **新闻统计页面**:
  - 一个用于展示 `NewsStatsView` 返回的统计数据的页面，可能包含图表或数据表格，以可视化每位人员的发文情况。
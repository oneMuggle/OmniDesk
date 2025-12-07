# 新闻发布功能设计方案

本文档详细描述了“新闻发布”功能的数据模型和 API 端点设计。

## 1. 数据模型设计

为了支持新闻发布功能，我们将创建两个核心模型：`NewsType` 和 `NewsArticle`。

### 1.1. `NewsType` 模型

该模型用于存储可自定义的新闻类型，方便对新闻进行分类管理。

-   **模型名称**: `NewsType`
-   **字段**:
    -   `id` (主键): `integer` - 唯一标识符。
    -   `name` (类型名称): `string` - 例如，“新闻稿”、“博客文章”、“媒体报道”。该字段应唯一。

**示例数据**:

```json
[
  { "id": 1, "name": "新闻稿" },
  { "id": 2, "name": "博客文章" }
]
```

### 1.2. `NewsArticle` 模型

该模型用于存储新闻文章的具体信息。

-   **模型名称**: `NewsArticle`
-   **字段**:
    -   `id` (主键): `integer` - 唯一标识符。
    -   `title` (标题): `string` - 文章的标题。
    -   `link` (链接): `string (URL)` - 指向新闻原文的链接。
    -   `publication_date` (发布日期): `date` - 文章发布的日期。
    -   `personnel` (关联人员): `foreign key` - 关联到 `Personnel` 或 `User` 模型，用于记录与此新闻相关的人员。
    -   `news_type` (新闻类型): `foreign key` - 关联到 `NewsType` 模型，用于指定文章的类型。

**示例数据**:

```json
{
  "id": 101,
  "title": "公司发布新的AI产品",
  "link": "https://example.com/news/ai-product-launch",
  "publication_date": "2023-10-27",
  "personnel_id": 5,
  "news_type_id": 1
}
```

## 2. API 端点设计

以下是为新闻类型和新闻文章管理设计的 RESTful API 端点。

### 2.1. 新闻类型管理 (NewsType)

-   **路径前缀**: `/api/news-types/`

#### `GET /api/news-types/`

-   **描述**: 获取所有新闻类型的列表。
-   **成功响应 (200 OK)**:
    ```json
    [
      { "id": 1, "name": "新闻稿" },
      { "id": 2, "name": "博客文章" }
    ]
    ```

#### `POST /api/news-types/`

-   **描述**: 创建一个新的新闻类型。
-   **请求体**:
    ```json
    {
      "name": "媒体报道"
    }
    ```
-   **成功响应 (201 Created)**:
    ```json
    {
      "id": 3,
      "name": "媒体报道"
    }
    ```

#### `PUT /api/news-types/<id>/`

-   **描述**: 更新一个指定的新闻类型。
-   **请求体**:
    ```json
    {
      "name": "行业分析"
    }
    ```
-   **成功响应 (200 OK)**:
    ```json
    {
      "id": 3,
      "name": "行业分析"
    }
    ```

#### `DELETE /api/news-types/<id>/`

-   **描述**: 删除一个指定的新闻类型。
-   **成功响应 (204 No Content)**: 无响应体。

### 2.2. 新闻文章管理 (NewsArticle)

-   **路径前缀**: `/api/news-articles/`

#### `GET /api/news-articles/`

-   **描述**: 获取新闻文章列表，支持筛选。
-   **查询参数**:
    -   `personnel_id` (可选): `integer` - 按人员ID筛选。
    -   `month` (可选): `string` (格式: `YYYY-MM`) - 按发布月份筛选。
    -   `type_id` (可选): `integer` - 按新闻类型ID筛选。
-   **成功响应 (200 OK)**:
    ```json
    [
      {
        "id": 101,
        "title": "公司发布新的AI产品",
        "link": "https://example.com/news/ai-product-launch",
        "publication_date": "2023-10-27",
        "personnel": { "id": 5, "name": "张三" },
        "news_type": { "id": 1, "name": "新闻稿" }
      }
    ]
    ```

#### `POST /api/news-articles/`

-   **描述**: 创建一篇新的新闻文章。
-   **请求体**:
    ```json
    {
      "title": "第二季度财报亮点",
      "link": "https://example.com/news/q2-earnings",
      "publication_date": "2023-10-28",
      "personnel_id": 6,
      "news_type_id": 2
    }
    ```
-   **成功响应 (201 Created)**:
    ```json
    {
      "id": 102,
      "title": "第二季度财报亮点",
      "link": "https://example.com/news/q2-earnings",
      "publication_date": "2023-10-28",
      "personnel_id": 6,
      "news_type_id": 2
    }
    ```

#### `PUT /api/news-articles/<id>/`

-   **描述**: 更新一篇指定的新闻文章。
-   **请求体**:
    ```json
    {
      "title": "更新：第二季度财报亮点",
      "link": "https://example.com/news/q2-earnings-updated",
      "publication_date": "2023-10-29",
      "personnel_id": 6,
      "news_type_id": 2
    }
    ```
-   **成功响应 (200 OK)**:
    ```json
    {
      "id": 102,
      "title": "更新：第二季度财报亮点",
      "link": "https://example.com/news/q2-earnings-updated",
      "publication_date": "2023-10-29",
      "personnel_id": 6,
      "news_type_id": 2
    }
    ```

#### `DELETE /api/news-articles/<id>/`

-   **描述**: 删除一篇指定的新闻文章。
-   **成功响应 (204 No Content)**: 无响应体。

### 2.3. 新闻统计

#### `GET /api/news-stats/`

-   **描述**: 获取新闻发布的统计数据。
-   **成功响应 (200 OK)**:
    -   `total_articles` (总文章数): `integer`
    -   `by_person_monthly` (每人每月的发文数量): `object`
        -   键为人员姓名或ID。
        -   值为一个对象，其中键为月份 (`YYYY-MM`)，值为该月的文章数量。

    **示例**:
    ```json
    {
      "total_articles": 150,
      "by_person_monthly": {
        "张三": {
          "2023-10": 5,
          "2023-09": 3
        },
        "李四": {
          "2023-10": 8
        }
      }
    }
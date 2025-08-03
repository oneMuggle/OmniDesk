# 电子书阅读器项目规划

## 项目总体规划

本项目的目标是实现一个现代化的电子书阅读器，允许用户阅读按章节拆分的Markdown文档、发表评论和进行划线批注。

计划分为三个主要部分：

1.  **数据处理与存储：** 将 `jibo.md` 文件解析并存入数据库。
2.  **后端API开发：** 使用 Django Rest Framework 提供数据接口。
3.  **前端页面开发：** 使用 React 构建一个现代化的、交互式的阅读界面。

---

## 详细计划

### 第一阶段：数据处理与存储

此阶段的目标是将 Markdown 文稿转换成结构化的数据，并存入数据库。

1.  **数据库模型设计：**
    在 `DRFForVue/documents/models.py` 中定义以下模型：
    *   `Book`: 用于表示书籍信息，比如书名。
    *   `Chapter`: 存储每个章节的信息，包括标题、Markdown原文、HTML内容、顺序等。它将与 `Book` 建立外键关系。
    *   `Comment`: 存储用户评论，与 `Chapter` 关联。
    *   `Annotation`: 存储用户的划线批注信息，包括选中的文本范围、批注内容，并与 `Chapter` 关联。

2.  **Markdown 解析脚本：**
    创建一个独立的 Python 脚本 (`scripts/parse_markdown.py`)，该脚本将：
    *   读取 `data/books/jiboguan/jibo.md` 文件。
    *   使用正则表达式或 Markdown 解析库（如 `mistune`）按 `<h1>` 和 `<h2>` 标签拆分章节。
    *   将每个章节的 Markdown 内容转换成 HTML。
    *   将解析出的章节数据存入数据库。

### 第二阶段：后端 API 开发

使用现有的 `DRFForVue` 项目来创建 API。

1.  **序列化器 (Serializers):**
    在 `DRFForVue/documents/serializers.py` 中为 `Chapter`、`Comment` 和 `Annotation` 模型创建序列化器。

2.  **视图 (Views) 和路由 (URLs):**
    在 `DRFForVue/documents/views.py` 和 `DRFForVue/documents/urls.py` 中创建以下 API 端点：
    *   `GET /api/documents/chapters/`: 获取所有章节的列表（标题、ID）。
    *   `GET /api/documents/chapters/<int:pk>/`: 获取单个章节的详细内容（HTML内容、评论、批注）。
    *   `POST /api/documents/chapters/<int:pk>/comments/`: 添加新评论。
    *   `POST /api/documents/chapters/<int:pk>/annotations/`: 添加新批注。

### 第三阶段：前端页面开发

在 `calendar_with_react` 项目中进行前端开发。

1.  **页面结构：**
    *   创建一个新的路由 `/book`。
    *   页面采用两栏布局：左侧为可折叠的章节目录，右侧为内容展示区。

2.  **组件设计：**
    *   `BookPage.jsx`: 主页面组件，管理整体布局和状态。
    *   `TableOfContents.jsx`: 渲染左侧的章节目录。
    *   `ChapterView.jsx`: 渲染右侧的章节内容，使用 `react-markdown` 或直接渲染 HTML。
    *   `Commenting.jsx`: 实现评论的显示和提交功能。
    *   `AnnotationHandler.jsx`: 处理文本选择、划线高亮和批注的添加与显示。

---

## 系统架构图 (Mermaid)

```mermaid
graph TD
    subgraph "用户浏览器"
        A[React App]
    end

    subgraph "Web 服务器"
        B[Django/DRF]
    end

    subgraph "数据库"
        C[PostgreSQL/SQLite]
    end

    subgraph "数据处理"
        D[Python脚本: parse_markdown.py]
    end

    E[jibo.md] --"读取"--> D
    D --"写入"--> C

    A --"API 请求 (获取章节/评论/批注)"--> B
    B --"API 响应"--> A

    B --"读/写数据"--> C

    A --"用户交互 (评论/划线)"--> B